import pandas as pd
import numpy as np

def check_null_columns(dataframes_dict):
    """
    Check which columns contain NULL values in each DataFrame
    
    Parameters:
    -----------
    dataframes_dict : dict
        Dictionary with table names as keys and DataFrames as values
    """
    null_report = {}
    
    for table_name, df in dataframes_dict.items():
        print(f"\n{'='*60}")
        print(f"Table: {table_name}")
        print(f"Total rows: {len(df)}")
        print(f"{'='*60}")
        
        null_info = {}
        
        for col in df.columns:
            null_count = df[col].isna().sum()
            if null_count > 0:
                null_pct = (null_count / len(df)) * 100
                null_info[col] = {
                    'null_count': null_count,
                    'null_percentage': null_pct,
                    'sample_non_null_values': df[df[col].notna()][col].value_counts().head(3).to_dict() if not df[df[col].notna()].empty else {}
                }
                
                print(f"\n  Column: {col}")
                print(f"    - Null count: {null_count:,} ({null_pct:.2f}%)")
                print(f"    - Non-null count: {len(df) - null_count:,}")
                
                # Show sample values
                if not df[df[col].notna()].empty:
                    print(f"    - Sample values: {list(df[df[col].notna()][col].unique()[:5])}")
        
        if not null_info:
            print("\n  ✓ No NULL values found in any column")
        
        null_report[table_name] = null_info
    
    return null_report

def check_unique_constraint_columns(dataframes_dict, constraints_dict):
    """
    Check for nulls specifically in columns that are part of unique constraints
    """
    print("\n" + "="*80)
    print("UNIQUE CONSTRAINT NULL CHECK")
    print("="*80)
    
    problematic_constraints = {}
    
    for table_name, unique_cols in constraints_dict.items():
        if table_name not in dataframes_dict:
            continue
            
        df = dataframes_dict[table_name]
        print(f"\n{table_name}:")
        print(f"  Unique constraint columns: {unique_cols}")
        
        # Check which columns actually exist in the dataframe
        existing_cols = [col for col in unique_cols if col in df.columns]
        missing_cols = [col for col in unique_cols if col not in df.columns]
        
        if missing_cols:
            print(f"  ⚠️  Missing columns in dataframe: {missing_cols}")
            # Try case-insensitive match
            for missing_col in missing_cols:
                found = False
                for df_col in df.columns:
                    if missing_col.lower() == df_col.lower():
                        print(f"      Found case mismatch: '{missing_col}' vs '{df_col}'")
                        existing_cols.append(df_col)
                        found = True
                        break
                if not found:
                    print(f"      Column '{missing_col}' not found at all!")
        
        problems = []
        for col in existing_cols:
            null_count = df[col].isna().sum()
            if null_count > 0:
                problems.append({
                    'column': col,
                    'null_count': null_count,
                    'null_percentage': (null_count / len(df)) * 100
                })
                print(f"  ⚠️  {col}: {null_count:,} nulls ({(null_count/len(df)*100):.2f}%)")
        
        if problems and existing_cols:
            problematic_constraints[table_name] = problems
            
            # Check how many rows would be excluded by the constraint
            try:
                mask = df[existing_cols].notna().all(axis=1)
                excluded_rows = len(df) - mask.sum()
                print(f"  ❌ Rows that would violate unique constraint: {excluded_rows:,} ({(excluded_rows/len(df)*100):.2f}%)")
            except KeyError as e:
                print(f"  ❌ Error checking constraint violations: {e}")
        elif not problems:
            print("  ✓ All unique constraint columns are non-null")
    
    return problematic_constraints

def analyze_fastf1_nulls(
    df_event_info, df_session_info, df_results, df_laps, 
    df_weather, df_car_data, df_pos_data, df_rcm, df_circuit_info, 
    df_track_status, df_session_status
):
    """
    Analyze all FastF1 dataframes for null values
    """
    
    # Create dictionary of dataframes
    dataframes = {
        'FastF1_EventInfo': df_event_info,
        'FastF1_SessionInfo': df_session_info,
        'FastF1_Results': df_results,
        'FastF1_Laps': df_laps,
        'FastF1_Weather': df_weather,
        'FastF1_CarData': df_car_data,
        'FastF1_PosData': df_pos_data,
        'FastF1_RaceControlMsg': df_rcm,
        'FastF1_CircuitInfo': df_circuit_info,
        'FastF1_TrackStatus': df_track_status,
        'FastF1_SessionStatus': df_session_status
    }
    
    # Define unique constraints
    unique_constraints = {
        'FastF1_EventInfo': ['Year', 'RoundNumber', 'TestNumber'],
        'FastF1_SessionInfo': ['SessionID'],
        'FastF1_Results': ['SessionId', 'DriverNumber'],
        'FastF1_Laps': ['SessionId', 'Session', 'Time', 'DriverNumber'],
        'FastF1_Weather': ['SessionId', 'Time'],
        'FastF1_CarData': ['SessionId', 'DriverNumber', 'Time', 'Source'],
        'FastF1_PosData': ['SessionId', 'DriverNumber', 'Time', 'Source'],
        'FastF1_RaceControlMsg': ['SessionId', 'Time', 'Category', 'Status', 'RacingNumber', 'Sector'],
        'FastF1_CircuitInfo': ['SessionId', 'Feature', 'Number', 'Letter'],
        'FastF1_TrackStatus': ['SessionId', 'Time'],
        'FastF1_SessionStatus': ['SessionId', 'Time', 'Status']
    }
    
    # Check all nulls
    null_report = check_null_columns(dataframes)
    
    # Check unique constraint issues
    constraint_issues = check_unique_constraint_columns(dataframes, unique_constraints)
    
    return null_report, constraint_issues