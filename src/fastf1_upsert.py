import pandas as pd
from sqlalchemy import create_engine, text
import fastf1_create_tables as f1_ct
import io
import numpy as np


def get_unique_constraints(engine, table_name, schema='public', exclude_list=['id']):
    """Get all unique constraints excluding id-only primary keys"""
    # Use the original query
    query = text("""
    SELECT 
        con.conname as constraint_name,
        array_agg(att.attname ORDER BY u.attposition) as columns
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
    JOIN unnest(con.conkey) WITH ORDINALITY AS u(attnum, attposition) ON true
    JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = u.attnum
    WHERE nsp.nspname = :schema
        AND rel.relname = :table_name
        AND con.contype IN ('u', 'p')  -- unique and primary key constraints
    GROUP BY con.conname, con.oid
    ORDER BY con.contype DESC, con.conname
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"schema": schema, "table_name": table_name})
        constraints = result.fetchall()
    
    
    # Filter out id-only constraints in Python
    filtered_constraints = []
    for name, cols in constraints:
        cols_list = list(cols)
        if cols_list != exclude_list:  # Exclude id-only constraints
            filtered_constraints.append((name, cols_list))
    
    return filtered_constraints


def convert_timedelta(df):
    """
    Convert timedelta columns for COPY - ensure they're strings in PostgreSQL interval format
    """
    df_copy = df.copy()
    
    for col in df_copy.columns:
        if df_copy[col].dtype == 'timedelta64[ns]':
            # Convert to PostgreSQL interval format
            df_copy[col] = df_copy[col].apply(
                lambda x: (
                    f"{x.days} days {x.seconds//3600:02d}:{(x.seconds%3600)//60:02d}:{x.seconds%60:02d}.{x.microseconds:06d}"
                    if pd.notna(x) else None
                )
            )
        elif df_copy[col].dtype == 'object' and len(df_copy) > 0:
            # Check if it's a string representation of timedelta
            first_val = df_copy[col].iloc[0]
            if pd.notna(first_val) and isinstance(first_val, str) and 'days' in str(first_val):
                # It's already in the right format, keep it
                pass
    
    return df_copy


def auto_upsert_df(df, table_name, engine, schema='public', on_conflict='skip', 
                         chunksize=10000, constraint_name=None):
    """
    Fixed version of auto_upsert_df that handles column ordering and type conversion properly
    
    Process:
    1. Get table definitions and fix column order
    2. Convert timedelta columns to PostgreSQL interval format
    3. Find appropriate unique constraints (excluding id-only constraints)
    4. Create temporary table matching target structure
    5. Use COPY to bulk load data into temp table
    6. INSERT from temp table with ON CONFLICT handling
    """
    
    # Step 1: Get table definitions and fix column order
    table_definitions = f1_ct.get_table_definitions()
    

    if table_name in table_definitions:
        # Get the column order from table definition
        table_def = table_definitions[table_name]
        # Fix integer columns that might be stored as float
        for col_name, col_type in table_def['columns'].items():
            if col_name in df.columns and 'SMALLINT' in col_type.upper():
                # Convert float to nullable integer
                df[col_name] = df[col_name].astype('Float64').astype('Int64')
                
        column_order = list(table_def['columns'].keys())
        
        # Filter to only columns that exist in both DataFrame and database
        # (excluding auto-generated columns like 'id')
        columns_to_use = [col for col in column_order 
                         if col in df.columns and col != 'id']
        
        df = df[columns_to_use]
    
    # Step 2: Convert timedelta columns to PostgreSQL interval format    
    df = convert_timedelta(df)
    
    # Step 3: Get unique constraints (excluding id-only constraints)
    constraints = get_unique_constraints(engine, table_name, schema)
    
    # Special handling for tables without suitable constraints
    if not constraints:
        if table_name == 'FastF1_RaceControlMsg':
            # RaceControlMsg has a unique index that might not show up in regular constraint query
            constraint_name = 'unique_rcm'
            unique_columns = ['SessionID', 'Time', 'Category', 'Message']
            print(f"  Using hardcoded constraint for {table_name}: {constraint_name}")
        else:
            print("  No suitable constraints found, using regular insert")
            try:
                df.to_sql(table_name, engine, schema=schema, if_exists='append', 
                         index=False, method='multi', chunksize=chunksize)
                return {'rows_affected': len(df), 'constraint_used': None}
            except Exception as e:
                print(f"  Regular insert failed: {e}")
                raise
    else:
        # Use the first available constraint
        constraint_name, unique_columns = constraints[0]
    
    print(f"Using constraint '{constraint_name}' with columns: {unique_columns}")
    
    # Verify all unique columns exist in DataFrame
    missing_cols = set(unique_columns) - set(df.columns)
    if missing_cols:
        # For RaceControlMsg, Message might be in the constraint but nullable
        if table_name == 'FastF1_RaceControlMsg' and missing_cols == {'Message'}:
            unique_columns = [col for col in unique_columns if col in df.columns]
        else:
            print(f"  Error: DataFrame missing required unique columns: {missing_cols}")
            print(f"  DataFrame columns: {list(df.columns)}")
            return {'rows_affected': 0, 'constraint_used': constraint_name, 'error': 'missing columns'}
    
    # Step 4-6: Process in chunks
    total_rows = 0
    chunks = np.array_split(df, max(1, len(df) // chunksize))
    
    for i, chunk_df in enumerate(chunks):
        if chunk_df.empty:
            continue
            
        print(f"Processing chunk {i+1}/{len(chunks)} ({len(chunk_df)} rows)...")
        
        conn = engine.raw_connection()
        try:
            cur = conn.cursor()
            
            # Create temp table name
            temp_table = f"temp_{table_name}_{i}"
            quoted_table = f'"{schema}"."{table_name}"'
            
            # Get column definitions from our table definitions
            if table_name in table_definitions:
                table_def = table_definitions[table_name]
                columns_def = []
                column_list = []
                
                for col_name, col_type in table_def['columns'].items():
                    # Skip auto-generated columns and columns not in DataFrame
                    if col_name != 'id' and col_name in chunk_df.columns:
                        # Clean up the column type for temp table
                        clean_type = col_type.split(' DEFAULT')[0].split(' PRIMARY KEY')[0]
                        columns_def.append(f'"{col_name}" {clean_type}')
                        column_list.append(col_name)
            
            # Create temp table
            create_temp_sql = f'CREATE TEMP TABLE "{temp_table}" ({", ".join(columns_def)})'
            cur.execute(create_temp_sql)
            
            # Prepare column list for COPY
            columns_str = ', '.join([f'"{c}"' for c in column_list])
            
            # Ensure chunk_df has columns in the right order
            chunk_df_ordered = chunk_df[column_list]
            
            # Prepare data for COPY
            output = io.StringIO()
            chunk_df_ordered.to_csv(output, sep='\t', header=False, index=False, na_rep='\\N')
            output.seek(0)
            
            # COPY data into temp table
            copy_sql = f'COPY "{temp_table}" ({columns_str}) FROM STDIN WITH (FORMAT CSV, DELIMITER E\'\\t\', NULL \'\\N\')'
            cur.copy_expert(copy_sql, output)
            
            # Build INSERT query based on conflict handling
            if on_conflict == 'skip':
                # Handle special case for RaceControlMsg with COALESCE
                if table_name == 'FastF1_RaceControlMsg':
                    conflict_cols = '"SessionID", "Time", "Category", COALESCE("Message", \'\')'
                else:
                    conflict_cols = ', '.join([f'"{c}"' for c in unique_columns])
                
                query = f"""
                INSERT INTO {quoted_table} ({columns_str})
                SELECT {columns_str} FROM "{temp_table}"
                ON CONFLICT ({conflict_cols}) 
                DO NOTHING
                """
                
            elif on_conflict == 'update':
                update_columns = [c for c in column_list if c not in unique_columns]
                
                if table_name == 'FastF1_RaceControlMsg':
                    conflict_cols = '"SessionID", "Time", "Category", COALESCE("Message", \'\')'
                else:
                    conflict_cols = ', '.join([f'"{c}"' for c in unique_columns])
                
                if update_columns:
                    set_clause = ', '.join([f'"{c}" = EXCLUDED."{c}"' for c in update_columns])
                    query = f"""
                    INSERT INTO {quoted_table} ({columns_str})
                    SELECT {columns_str} FROM "{temp_table}"
                    ON CONFLICT ({conflict_cols}) 
                    DO UPDATE SET {set_clause}
                    """
                else:
                    # No columns to update
                    query = f"""
                    INSERT INTO {quoted_table} ({columns_str})
                    SELECT {columns_str} FROM "{temp_table}"
                    ON CONFLICT ({conflict_cols}) 
                    DO NOTHING
                    """
                    
            else:  # on_conflict == 'error'
                query = f"""
                INSERT INTO {quoted_table} ({columns_str})
                SELECT {columns_str} FROM "{temp_table}"
                """
            
            # Execute the INSERT query
            cur.execute(query)
            rows_affected = cur.rowcount
            total_rows += rows_affected
            
            # Clean up temp table
            cur.execute(f'DROP TABLE IF EXISTS "{temp_table}"')
            
            conn.commit()
            print(f"  Chunk complete: {rows_affected} rows affected")
            
        except Exception as e:
            conn.rollback()
            print(f"  Error in chunk {i+1}: {e}")
            raise
        finally:
            cur.close()
            conn.close()
    
    result = {
        'rows_affected': total_rows,
        'constraint_used': constraint_name,
        'unique_columns': unique_columns,
        'total_input_rows': len(df),
        'action': on_conflict
    }
    
    print(f"Operation complete: {total_rows}/{len(df)} rows affected using '{constraint_name}'")
    
    return result


# Helper function to find the correct case for table names
def find_table_exact_name(engine, table_pattern, schema='public'):
    """Find the exact case-sensitive name of a table"""
    query = text("""
    SELECT tablename 
    FROM pg_tables 
    WHERE schemaname = :schema 
    AND LOWER(tablename) = LOWER(:pattern)
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"schema": schema, "pattern": table_pattern})
        row = result.fetchone()
        return row[0] if row else None


def prepare_dataframes_for_insert(dataframes_dict):
    """
    Prepare dataframes for insertion with proper data types and column order
    """
    prepared_dfs = {}
    
    for table_name, df in dataframes_dict.items():
        df_copy = df.copy()

        # Handle common data type conversions
        if 'Position' in df_copy.columns:
            df_copy['Position'] = df_copy['Position'].apply(
                lambda x: int(x) if pd.notna(x) else None
            )
        
        if 'GridPosition' in df_copy.columns:
            df_copy['GridPosition'] = df_copy['GridPosition'].apply(
                lambda x: int(x) if pd.notna(x) else None
            )
        
        if 'Laps' in df_copy.columns:
            df_copy['Laps'] = df_copy['Laps'].apply(
                lambda x: int(x) if pd.notna(x) else None
            )
        
        # Handle Laps table specific conversions
        if table_name == 'FastF1_Laps':
            # Convert float lap numbers and stints to integers
            if 'LapNumber' in df_copy.columns:
                df_copy['LapNumber'] = df_copy['LapNumber'].apply(
                    lambda x: int(x) if pd.notna(x) else None
                )
            
            if 'Stint' in df_copy.columns:
                df_copy['Stint'] = df_copy['Stint'].apply(
                    lambda x: int(x) if pd.notna(x) else None
                )
            
            if 'TyreLife' in df_copy.columns:
                df_copy['TyreLife'] = df_copy['TyreLife'].apply(
                    lambda x: int(x) if pd.notna(x) else None
                )
            
            # Also handle Position in laps (it's different from Results.Position)
            if 'Position' in df_copy.columns:
                df_copy['Position'] = df_copy['Position'].apply(
                    lambda x: int(x) if pd.notna(x) else None
                )
        
        # Handle TestNumber for EventInfo
        elif table_name == 'FastF1_EventInfo':
            if 'TestNumber' in df_copy.columns:
                df_copy['TestNumber'] = df_copy['TestNumber'].fillna(-1).astype('Int64')
        
        # Handle RaceControlMsg
        elif table_name == 'FastF1_RaceControlMsg':
            if 'Status' in df_copy.columns:
                df_copy['Status'] = df_copy['Status'].fillna('')
            if 'RacingNumber' in df_copy.columns:
                df_copy['RacingNumber'] = df_copy['RacingNumber'].fillna('')
            if 'Sector' in df_copy.columns:
                df_copy['Sector'] = df_copy['Sector'].apply(
                    lambda x: int(x) if pd.notna(x) else -1
                )
            if 'Lap' in df_copy.columns:
                # Lap in RaceControlMsg should also be integer
                df_copy['Lap'] = df_copy['Lap'].apply(
                    lambda x: int(x) if pd.notna(x) else None
                )
            # Remove 'id' column if it exists
            if 'id' in df_copy.columns:
                df_copy.drop('id', axis=1, inplace=True)
        
        # Handle CarData and PosData
        elif table_name in ['FastF1_CarData', 'FastF1_PosData']:
            # nGear should be SMALLINT
            if 'nGear' in df_copy.columns:
                df_copy['nGear'] = df_copy['nGear'].apply(
                    lambda x: int(x) if pd.notna(x) else None
                )
            
            # DRS should be SMALLINT
            if 'DRS' in df_copy.columns:
                df_copy['DRS'] = df_copy['DRS'].apply(
                    lambda x: int(x) if pd.notna(x) else None
                )
            
            # Fix Date column issues
            if 'Date' in df_copy.columns:
                if pd.api.types.is_timedelta64_dtype(df_copy['Date']):
                    print(f"  Warning: {table_name} has timedelta in Date column, setting to NULL")
                    df_copy['Date'] = pd.NaT
            
            # Remove 'id' column if it exists
            if 'id' in df_copy.columns:
                df_copy.drop('id', axis=1, inplace=True)
        
        # Handle Weather table
        elif table_name == 'FastF1_Weather':
            if 'WindDirection' in df_copy.columns:
                df_copy['WindDirection'] = df_copy['WindDirection'].apply(
                    lambda x: int(x) if pd.notna(x) else None
                )
        
        # Remove 'id' from tables with surrogate keys
        if 'id' in df_copy.columns and table_name in ['FastF1_Laps']:
            df_copy.drop('id', axis=1, inplace=True)
        
        prepared_dfs[table_name] = df_copy
    
    return prepared_dfs

def fix_dataframe_column_names(dataframes_dict):
    """
    Fix column names to use SessionID (capital D) consistently
    """
    fixed_dfs = {}
    
    for table_name, df in dataframes_dict.items():
        df_copy = df.copy()
        
        # Rename SessionId to SessionID in all tables
        if 'SessionId' in df_copy.columns:
            print(f"Renaming SessionId to SessionID in {table_name}")
            df_copy.rename(columns={'SessionId': 'SessionID'}, inplace=True)
        
        # Also handle lowercase variations
        for col in df_copy.columns:
            if col.lower() == 'sessionid' and col != 'SessionID':
                print(f"Renaming {col} to SessionID in {table_name}")
                df_copy.rename(columns={col: 'SessionID'}, inplace=True)
        
        # Also fix other ID columns for consistency
        id_mappings = {
            'DriverId': 'DriverID',
            'TeamId': 'TeamID',
            'EventId': 'EventID',
            'CountryId': 'CountryID',
            'CircuitId': 'CircuitID'
        }
        
        for old_name, new_name in id_mappings.items():
            if old_name in df_copy.columns:
                print(f"Renaming {old_name} to {new_name} in {table_name}")
                df_copy.rename(columns={old_name: new_name}, inplace=True)
        
        fixed_dfs[table_name] = df_copy
    
    return fixed_dfs

def reorder_dataframe_columns(df, table_name, engine, schema='public'):
    """
    Reorder DataFrame columns to match database table column order
    """
    # Get the actual column order from the database
    query = text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = :schema
        AND table_name = :table_name
        ORDER BY ordinal_position
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"schema": schema, "table_name": table_name})
        db_columns = [row[0] for row in result]
    
    # Filter to only columns that exist in both DataFrame and database
    # (excluding auto-generated columns like 'id')
    common_columns = [col for col in db_columns if col in df.columns]
    
    # Reorder the DataFrame
    return df[common_columns]


# Example usage with your case-sensitive table names:
if __name__ == "__main__":
    ...
    # engine = create_engine('postgresql://user:password@localhost:5432/mydb')
    
    # # For your FastF1 tables:
    # tables_to_process = [
    #     ('FastF1_Results', df_results),
    #     ('FastF1_Laps', df_laps),
    #     ('FastF1_Weather', df_weather),
    #     ('FastF1_Telemetry', df_telemetry),
    #     ('FastF1_RaceControlMsg', df_rcm),
    #     ('FastF1_CircuitInfo', df_ci),
    #     ('FastF1_TrackStatus', df_ts),
    #     ('FastF1_SessionStatus', df_ss),
    #     ('FastF1_Schedule', df_schedule)
    # ]
    
    # for table_name, df in tables_to_process:
    #     print(f"\nProcessing {table_name}...")
    #     try:
    #         result = auto_upsert_df(df, table_name, engine, on_conflict='skip')
    #         print(f"Success: {result}")
    #     except Exception as e:
    #         print(f"Error processing {table_name}: {e}")