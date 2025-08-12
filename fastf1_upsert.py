import pandas as pd
from sqlalchemy import create_engine, text
import fastf1_create_tables as f1_ct
import io
import numpy as np

def get_unique_constraints(engine, table_name, schema='public'):
    """Get all unique constraints for a table including composite constraints"""
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
    
    return [(name, list(cols)) for name, cols in constraints]

def get_unique_constraints_no_id(engine, table_name, schema='public'):
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
        if cols_list != ['id']:  # Exclude id-only constraints
            filtered_constraints.append((name, cols_list))
    
    return filtered_constraints

def convert_timedelta(df):
    for col in df.select_dtypes(include=["timedelta64"]).columns:
        df[col] = df[col].apply(
            lambda x: (
                f"{x.days} days {x.seconds//3600:02d}:{(x.seconds%3600)//60:02d}:{x.seconds%60:02d}.{x.microseconds:06d}"
                if pd.notna(x)
                else None
            )
        )
    return df

def convert_timedelta_in_copy(df):
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
                         chunksize=10000, constraint_name=None, prefer_unique=True):
    """
    Automatically upsert DataFrame to PostgreSQL table with composite unique constraint handling
    
    Parameters:
    -----------
    df : pandas.DataFrame
        DataFrame to insert/update
    table_name : str
        Target table name (case-sensitive)
    engine : sqlalchemy.engine
        SQLAlchemy engine
    schema : str
        Database schema (default: 'public')
    on_conflict : str
        How to handle conflicts: 'skip', 'update', or 'error' (default: 'skip')
    chunksize : int
        Number of rows to process at once (default: 10000)
    constraint_name : str, optional
        Specific constraint to use. If None, uses first unique constraint found
    
    Returns:
    --------
    dict : Information about the operation (rows affected, constraint used, etc.)
    """
    
   # Convert timedelta values to strings that can be inserted into an INTERVAL type column
    df = convert_timedelta(df)
    
    # Validate on_conflict parameter
    if on_conflict not in ['skip', 'update', 'error']:
        raise ValueError("on_conflict must be 'skip', 'update', or 'error'")
    
    # Get unique constraints
    constraints = get_unique_constraints_no_id(engine, table_name, schema)
    
    if not constraints:
        if on_conflict == 'error':
            raise ValueError(f"No unique constraints found for table {schema}.{table_name}")
        else:
            # No constraints, just do regular insert
            print("Warning: No unique constraints found. Performing regular insert.")
            df.to_sql(table_name, engine, schema=schema, if_exists='append', 
                     index=False, method='multi', chunksize=chunksize)
            return {'rows_affected': len(df), 'constraint_used': None}
    
    # Filter out constraints that only contain 'id' if prefer_unique is True
    if prefer_unique and len(constraints) > 1:
        non_id_constraints = [c for c in constraints if c[1] != ['id']]
        if non_id_constraints:
            constraints = non_id_constraints
    
    # Select constraint to use
    if constraint_name:
        constraint = next((c for c in constraints if c[0] == constraint_name), None)
        if not constraint:
            available = ', '.join([c[0] for c in constraints])
            raise ValueError(f"Constraint '{constraint_name}' not found. Available: {available}")
    else:
        # Use first non-id constraint if available
        constraint = constraints[0]
    
    constraint_name, unique_columns = constraint
    print(f"Using constraint '{constraint_name}' with columns: {unique_columns}")
    
    # Skip if constraint only has 'id' column and DataFrame doesn't have it
    if unique_columns == ['id'] and 'id' not in df.columns:
        print("  Skipping constraint check - DataFrame doesn't have 'id' column")
        # Just do regular insert without constraint checking
        df.to_sql(table_name, engine, schema=schema, if_exists='append', 
                 index=False, method='multi', chunksize=chunksize)
        return {'rows_affected': len(df), 'constraint_used': None}
    
    # Ensure all unique columns exist in DataFrame
    missing_cols = set(unique_columns) - set(df.columns)
    if missing_cols:
        print(f"  Error: DataFrame missing required unique columns: {missing_cols}")
        print(f"  DataFrame columns: {list(df.columns)}")
        return {'rows_affected': 0, 'constraint_used': constraint_name, 'error': 'missing columns'}
    
    
    # Process in chunks for better memory management
    total_rows = 0
    chunks = np.array_split(df, max(1, len(df) // chunksize))
    
    for i, chunk_df in enumerate(chunks):
        if chunk_df.empty:
            continue
            
        print(f"Processing chunk {i+1}/{len(chunks)} ({len(chunk_df)} rows)...")
        
        conn = engine.raw_connection()
        try:
            cur = conn.cursor()
            
            # Create temp table - properly quote the table name
            temp_table = f"temp_{table_name}_{i}"
            quoted_table = f'"{schema}"."{table_name}"'
            cur.execute(f'CREATE TEMP TABLE "{temp_table}" (LIKE {quoted_table} INCLUDING ALL)')
            
            # Use COPY to load data into temp table
            output = io.StringIO()
            chunk_df.to_csv(output, sep='\t', header=False, index=False, na_rep='\\N')
            output.seek(0)
            
            cur.copy_expert(
                f'COPY "{temp_table}" FROM STDIN WITH (FORMAT CSV, DELIMITER E\'\\t\', NULL \'\\N\')', 
                output
            )
            
            # Build the appropriate query based on on_conflict setting
            columns = chunk_df.columns.tolist()
            columns_str = ', '.join([f'"{c}"' for c in columns])
            
            if on_conflict == 'skip':
                # Insert and ignore conflicts
                query = f"""
                INSERT INTO {quoted_table} ({columns_str})
                SELECT {columns_str} FROM "{temp_table}"
                ON CONFLICT ({', '.join([f'"{c}"' for c in unique_columns])}) 
                DO NOTHING
                """
            
            elif on_conflict == 'update':
                # Insert and update on conflict
                update_columns = [c for c in columns if c not in unique_columns]
                
                if update_columns:
                    set_clause = ', '.join([f'"{c}" = EXCLUDED."{c}"' for c in update_columns])
                    query = f"""
                    INSERT INTO {quoted_table} ({columns_str})
                    SELECT {columns_str} FROM "{temp_table}"
                    ON CONFLICT ({', '.join([f'"{c}"' for c in unique_columns])}) 
                    DO UPDATE SET {set_clause}
                    """
                else:
                    # All columns are part of unique constraint, nothing to update
                    query = f"""
                    INSERT INTO {quoted_table} ({columns_str})
                    SELECT {columns_str} FROM "{temp_table}"
                    ON CONFLICT ({', '.join([f'"{c}"' for c in unique_columns])}) 
                    DO NOTHING
                    """
            
            else:  # on_conflict == 'error'
                # Let it fail on conflict
                query = f"""
                INSERT INTO {quoted_table} ({columns_str})
                SELECT {columns_str} FROM "{temp_table}"
                """
            
            # Execute the query
            cur.execute(query)
            rows_affected = cur.rowcount
            total_rows += rows_affected
            
            # Clean up temp table
            cur.execute(f'DROP TABLE IF EXISTS "{temp_table}"')
            
            conn.commit()
            print(f"  Chunk complete: {rows_affected} rows affected")
            
        except Exception as e:
            conn.rollback()
            raise e
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
    
    print(f"\nOperation complete: {total_rows}/{len(df)} rows affected using '{constraint_name}'")
    
    return result

def auto_upsert_df_fixed(df, table_name, engine, schema='public', on_conflict='skip', 
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
    for col in df.columns:
        if df[col].dtype == 'timedelta64[ns]':
            df[col] = df[col].apply(
                lambda x: (
                    f"{x.days} days {x.seconds//3600:02d}:{(x.seconds%3600)//60:02d}:{x.seconds%60:02d}.{x.microseconds:06d}"
                    if pd.notna(x) else None
                )
            )
    
    # Step 3: Get unique constraints (excluding id-only constraints)
    constraints = get_unique_constraints_no_id(engine, table_name, schema)
    
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

# Convenience wrapper functions
def insert_skip_conflicts(df, table_name, engine, **kwargs):
    """Insert rows, skipping any that violate unique constraints"""
    return auto_upsert_df(df, table_name, engine, on_conflict='skip', **kwargs)

def upsert_on_conflict(df, table_name, engine, **kwargs):
    """Insert rows, updating existing ones on unique constraint conflict"""
    return auto_upsert_df(df, table_name, engine, on_conflict='update', **kwargs)

def insert_or_fail(df, table_name, engine, **kwargs):
    """Insert rows, failing if any unique constraint is violated"""
    return auto_upsert_df(df, table_name, engine, on_conflict='error', **kwargs)


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

def prepare_fastf1_data_for_db(dataframes_dict):
    """
    Prepare FastF1 dataframes for database insertion by handling nulls
    """
    prepared_dfs = {}
    
    for table_name, df in dataframes_dict.items():
        df_copy = df.copy()
        
        if table_name == 'FastF1_EventInfo' and 'TestNumber' in df_copy.columns:
            # Use -1 for non-test events
            df_copy['TestNumber'] = df_copy['TestNumber'].fillna(-1).astype('Int64')
            
        elif table_name == 'FastF1_RaceControlMsg':
            if 'Status' in df_copy.columns:
                df_copy['Status'] = df_copy['Status'].fillna('')
            if 'RacingNumber' in df_copy.columns:
                df_copy['RacingNumber'] = df_copy['RacingNumber'].fillna('')
            if 'Sector' in df_copy.columns:
                df_copy['Sector'] = df_copy['Sector'].fillna(-1).astype('Int64')
                
        elif table_name == 'FastF1_SessionInfo':
            # Handle column name mismatch if needed
            if 'SessionId' in df_copy.columns and 'SessionID' not in df_copy.columns:
                df_copy['SessionID'] = df_copy['SessionId']
                
        elif table_name in ['FastF1_CarData', 'FastF1_PosData']:
            # Handle any nulls in the new telemetry tables if needed
            # For example, RelativeDistance might have nulls
            if 'RelativeDistance' in df_copy.columns:
                df_copy['RelativeDistance'] = df_copy['RelativeDistance'].fillna(0.0)
        
        prepared_dfs[table_name] = df_copy
    
    return prepared_dfs

def prepare_dataframes_for_insert(dataframes_dict):
    """
    Prepare dataframes for insertion with proper data types and column order
    """
    prepared_dfs = {}
    
    for table_name, df in dataframes_dict.items():
        df_copy = df.copy()
        #print(df_copy.columns)
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

def fix_copy_column_order(df, table_name):
    """
    Fix the column order issue for COPY command using table definitions
    """
    table_definitions = f1_ct.get_table_definitions()
    
    if table_name in table_definitions:
        # Get the column order from table definition
        table_def = table_definitions[table_name]
        column_order = list(table_def['columns'].keys())
        
        # Filter out auto-generated columns and columns not in DataFrame
        columns_to_use = [col for col in column_order 
                         if col in df.columns and col != 'id']
        
        return df[columns_to_use]
    
    return df

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