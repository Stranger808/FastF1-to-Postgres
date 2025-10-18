# -*- coding: utf-8 -*-
"""
Created on Sun Aug  3 02:46:21 2025

@author: bradl
"""

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql


def completely_drop_all_tables(engine, schema='public'):
    """
    Completely drop all FastF1 tables including all constraints
    """
    tables = [
        'FastF1_EventInfo', 'FastF1_SessionInfo', 'FastF1_Results',
        'FastF1_Laps', 'FastF1_Weather', 'FastF1_CarData', 'FastF1_PosData',
        'FastF1_RaceControlMsg', 'FastF1_CircuitInfo',
        'FastF1_TrackStatus', 'FastF1_SessionStatus'
    ]
    
    print("=== COMPLETELY DROPPING ALL FASTF1 TABLES ===\n")
    
    with engine.begin() as conn:
        # First, drop all foreign key constraints that might reference these tables
        fk_drop_query = text("""
            SELECT 
                'ALTER TABLE "' || n.nspname || '"."' || c.relname || '" DROP CONSTRAINT "' || con.conname || '" CASCADE;' as drop_cmd
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE con.contype = 'f'
            AND n.nspname = :schema
            AND c.relname = ANY(:tables)
        """)
        
        try:
            fk_drops = conn.execute(fk_drop_query, {"schema": schema, "tables": tables})
            for (drop_cmd,) in fk_drops:
                conn.execute(text(drop_cmd))
                print("  ✓ Dropped foreign key constraint")
        except Exception as e:
            print(f"  - Error dropping foreign keys: {e}")
        
        # Now drop each table with CASCADE
        for table_name in tables:
            try:
                conn.execute(text(f'DROP TABLE IF EXISTS "{schema}"."{table_name}" CASCADE'))
                print(f"  ✓ Dropped table: {table_name}")
            except Exception as e:
                print(f"  ✗ Error dropping table {table_name}: {e}")
    
    print("\n✅ All tables dropped completely!")

def verify_no_constraints(engine, schema='public'):
    """
    Verify that no FastF1 constraints exist
    """
    tables = [
        'FastF1_EventInfo', 'FastF1_SessionInfo', 'FastF1_Results',
        'FastF1_Laps', 'FastF1_Weather', 'FastF1_CarData', 'FastF1_PosData',
        'FastF1_RaceControlMsg', 'FastF1_CircuitInfo',
        'FastF1_TrackStatus', 'FastF1_SessionStatus'
    ]
    
    with engine.connect() as conn:
        # Check for any constraints
        constraint_query = text("""
            SELECT 
                c.relname as table_name,
                con.conname as constraint_name,
                con.contype as constraint_type
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = :schema
            AND c.relname = ANY(:tables)
            ORDER BY c.relname, con.conname
        """)
        
        constraints = conn.execute(constraint_query, {"schema": schema, "tables": tables})
        constraint_list = list(constraints)
        
        if constraint_list:
            print("\n⚠️ Found existing constraints:")
            for table, constraint, ctype in constraint_list:
                print(f"  - {table}.{constraint} (type: {ctype})")
            return False
        else:
            print("\n✓ No constraints found for FastF1 tables")
            return True

def clean_slate_recreate_tables(engine, schema='public'):
    """
    Complete clean slate recreation of all tables
    """
    print("=== CLEAN SLATE DATABASE RECREATION ===\n")
    
    # Step 1: Completely drop all tables
    completely_drop_all_tables(engine, schema)
    
    # Step 2: Verify no constraints remain
    verify_no_constraints(engine, schema)
    
    # Step 3: Create fresh tables
    print("\n=== CREATING FRESH TABLES ===")
    create_fastf1_tables_without_constraints(engine, schema)
    
    # Step 4: Add constraints
    print("\n=== ADDING CONSTRAINTS ===")
    add_constraints_to_tables(engine, schema)
    
    # Step 5: Create indexes and foreign keys
    print("\n=== CREATING INDEXES AND FOREIGN KEYS ===")
    create_indexes_and_foreign_keys(engine, schema)
    
    # Step 6: Analyze tables
    print("\n=== ANALYZING TABLES ===")
    analyze_tables(engine, schema)
    
    print("\n✅ Clean slate recreation complete!")
    
    return get_dtype_mappings()

def drop_all_constraints_and_indexes(engine, schema='public'):
    """
    Drop all constraints and indexes for FastF1 tables
    """
    
    tables = [
       'FastF1_EventInfo', 'FastF1_SessionInfo', 'FastF1_Results',
       'FastF1_Laps', 'FastF1_Weather', 'FastF1_CarData', 'FastF1_PosData',
       'FastF1_RaceControlMsg', 'FastF1_CircuitInfo',
       'FastF1_TrackStatus', 'FastF1_SessionStatus'
   ]
    
    with engine.begin() as conn:
        for table_name in tables:
            print(f"\nCleaning up {table_name}...")
            
            # Check if table exists
            table_exists_query = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = :schema 
                    AND table_name = :table_name
                )
            """)
            result = conn.execute(table_exists_query, {"schema": schema, "table_name": table_name})
            
            if not result.scalar():
                print(f"  - Table {table_name} does not exist, skipping...")
                continue
            
            # 1. Drop all foreign key constraints
            fk_query = text("""
                SELECT conname
                FROM pg_constraint pc
                JOIN pg_class c ON c.oid = pc.conrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = :schema
                AND c.relname = :table_name
                AND pc.contype = 'f'
            """)
            
            try:
                fk_constraints = conn.execute(fk_query, {"schema": schema, "table_name": table_name})
                for (constraint_name,) in fk_constraints:
                    conn.execute(text(f'ALTER TABLE "{schema}"."{table_name}" DROP CONSTRAINT IF EXISTS "{constraint_name}" CASCADE'))
                    print(f"  ✓ Dropped foreign key: {constraint_name}")
            except Exception as e:
                print(f"  - Error dropping foreign keys: {e}")
            
            # 2. Drop primary key
            try:
                # Get the actual primary key name
                pk_query = text("""
                    SELECT conname
                    FROM pg_constraint pc
                    JOIN pg_class c ON c.oid = pc.conrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = :schema
                    AND c.relname = :table_name
                    AND pc.contype = 'p'
                """)
                pk_result = conn.execute(pk_query, {"schema": schema, "table_name": table_name})
                pk_name = pk_result.scalar()
                
                if pk_name:
                    conn.execute(text(f'ALTER TABLE "{schema}"."{table_name}" DROP CONSTRAINT IF EXISTS "{pk_name}" CASCADE'))
                    print(f"  ✓ Dropped primary key: {pk_name}")
            except Exception as e:
                print(f"  - Error dropping primary key: {e}")
            
            # 3. Drop all unique constraints
            unique_query = text("""
                SELECT conname
                FROM pg_constraint pc
                JOIN pg_class c ON c.oid = pc.conrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = :schema
                AND c.relname = :table_name
                AND pc.contype = 'u'
            """)
            
            try:
                unique_constraints = conn.execute(unique_query, {"schema": schema, "table_name": table_name})
                for (constraint_name,) in unique_constraints:
                    conn.execute(text(f'ALTER TABLE "{schema}"."{table_name}" DROP CONSTRAINT IF EXISTS "{constraint_name}" CASCADE'))
                    print(f"  ✓ Dropped unique constraint: {constraint_name}")
            except Exception as e:
                print(f"  - Error dropping unique constraints: {e}")
            
            # 4. Drop all indexes (including unique indexes)
            index_query = text("""
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = :schema
                AND tablename = :table_name
                AND indexname NOT LIKE '%_pkey'
            """)
            
            try:
                indexes = conn.execute(index_query, {"schema": schema, "table_name": table_name})
                for (index_name,) in indexes:
                    conn.execute(text(f'DROP INDEX IF EXISTS "{schema}"."{index_name}" CASCADE'))
                    print(f"  ✓ Dropped index: {index_name}")
            except Exception as e:
                print(f"  - Error dropping indexes: {e}")



def get_table_definitions():
    """
    Return the table definitions used for creating tables
    This serves as the single source of truth for column order
    """
    return {
        'FastF1_EventInfo': {
            'columns': {
                "EventID": "INTEGER",
                "CountryID": "INTEGER",
                "CircuitID": "INTEGER",
                "Year": "INTEGER NOT NULL",
                "RoundNumber": "SMALLINT NOT NULL",
                "TestNumber": "SMALLINT",
                "Country": "TEXT",
                "CountryCode": "TEXT",
                "Location": "TEXT",
                "Circuit": "TEXT",
                "OfficialEventName": "TEXT",
                "EventDate": "TIMESTAMP",
                "EventName": "TEXT",
                "EventFormat": "TEXT",
                "Session1": "TEXT",
                "Session1Date": "TIMESTAMP",
                "Session1DateUtc": "TIMESTAMP",
                "Session2": "TEXT",
                "Session2Date": "TIMESTAMP",
                "Session2DateUtc": "TIMESTAMP",
                "Session3": "TEXT",
                "Session3Date": "TIMESTAMP",
                "Session3DateUtc": "TIMESTAMP",
                "Session4": "TEXT",
                "Session4Date": "TIMESTAMP",
                "Session4DateUtc": "TIMESTAMP",
                "Session5": "TEXT",
                "Session5Date": "TIMESTAMP",
                "Session5DateUtc": "TIMESTAMP",
                "F1ApiSupport": "BOOLEAN"
            }
        },
        'FastF1_SessionInfo': {
            'columns': {
                'SessionID': 'INTEGER PRIMARY KEY',
                'EventID': 'INTEGER',
                'SessionName': 'TEXT',
                'SessionType': 'TEXT',
                'StartDate': 'TIMESTAMP',
                'EndDate': 'TIMESTAMP',
                'GmtOffset': 'INTERVAL',
                'Time0': 'TIMESTAMP',
                'StartTime': 'INTERVAL',
                'ScheduledLaps': 'SMALLINT'
            }
        },
        'FastF1_Results': {
            'columns': {
                "SessionID": "INTEGER NOT NULL",
                "DriverNumber": "TEXT NOT NULL",
                "BroadcastName": "TEXT",
                "Abbreviation": "TEXT",
                "DriverID": "TEXT",
                "TeamName": "TEXT",
                "TeamColor": "TEXT",
                "TeamID": "TEXT",
                "FirstName": "TEXT",
                "LastName": "TEXT",
                "FullName": "TEXT",
                "HeadshotUrl": "TEXT",
                "CountryCode": "TEXT",
                "Position": "SMALLINT",
                "ClassifiedPosition": "TEXT",
                "GridPosition": "SMALLINT",
                "Q1": "INTERVAL",
                "Q2": "INTERVAL",
                "Q3": "INTERVAL",
                "Time": "INTERVAL",
                "Status": "TEXT",
                "Points": "FLOAT",
                "Laps": "SMALLINT"
            }
        },
        'FastF1_Laps': {
            'columns': {
                "id": "BIGSERIAL PRIMARY KEY",
                "SessionID": "INTEGER NOT NULL",
                "Session": "TEXT NOT NULL",
                "Time": "INTERVAL NOT NULL",
                "Driver": "TEXT",
                "DriverNumber": "TEXT NOT NULL",
                "LapTime": "INTERVAL",
                "LapNumber": "SMALLINT",
                "Stint": "SMALLINT",
                "PitOutTime": "INTERVAL",
                "PitInTime": "INTERVAL",
                "Sector1Time": "INTERVAL",
                "Sector2Time": "INTERVAL",
                "Sector3Time": "INTERVAL",
                "Sector1SessionTime": "INTERVAL",
                "Sector2SessionTime": "INTERVAL",
                "Sector3SessionTime": "INTERVAL",
                "SpeedI1": "FLOAT",
                "SpeedI2": "FLOAT",
                "SpeedFL": "FLOAT",
                "SpeedST": "FLOAT",
                "IsPersonalBest": "BOOLEAN DEFAULT FALSE",
                "Compound": "TEXT",
                "TyreLife": "SMALLINT",
                "FreshTyre": "BOOLEAN",
                "Team": "TEXT",
                "LapStartTime": "INTERVAL",
                "LapStartDate": "TIMESTAMP",
                "TrackStatus": "TEXT",
                "Position": "SMALLINT",
                "Deleted": "BOOLEAN DEFAULT FALSE",
                "DeletedReason": "TEXT DEFAULT ''",
                "FastF1Generated": "BOOLEAN DEFAULT FALSE",
                "IsAccurate": "BOOLEAN DEFAULT TRUE"
            }
        },
        'FastF1_Weather': {
            'columns': {
                "SessionID": "INTEGER NOT NULL",
                "Time": "INTERVAL NOT NULL",
                "AirTemp": "FLOAT",
                "Humidity": "FLOAT",
                "Pressure": "FLOAT",
                "Rainfall": "BOOLEAN",
                "TrackTemp": "FLOAT",
                "WindDirection": "SMALLINT",
                "WindSpeed": "FLOAT"
            }
        },
        'FastF1_CarData': {
            'columns': {
                "id": "BIGSERIAL PRIMARY KEY",
                "SessionID": "INTEGER NOT NULL",
                "DriverNumber": "TEXT NOT NULL",
                "Date": "TIMESTAMP",
                "SessionTime": "INTERVAL",
                "Time": "INTERVAL NOT NULL",
                "Source": "TEXT NOT NULL",
                "RPM": "FLOAT",
                "Speed": "FLOAT",
                "nGear": "SMALLINT",
                "Throttle": "FLOAT",
                "Brake": "BOOLEAN",
                "DRS": "SMALLINT",
                "DriverAhead": "TEXT",
                "DistanceToDriverAhead": "FLOAT",
                "Distance": "FLOAT",
                "RelativeDistance": "FLOAT"
            }
        },
        'FastF1_PosData': {
            'columns': {
                "id": "BIGSERIAL PRIMARY KEY",
                "SessionID": "INTEGER NOT NULL",
                "DriverNumber": "TEXT NOT NULL",
                "Date": "TIMESTAMP",
                "SessionTime": "INTERVAL",
                "Time": "INTERVAL NOT NULL",
                "Source": "TEXT NOT NULL",
                "Status": "TEXT",
                "X": "FLOAT",
                "Y": "FLOAT",
                "Z": "FLOAT"
            }
        },
        'FastF1_RaceControlMsg': {
            'columns': {
                "id": "BIGSERIAL PRIMARY KEY",
                "SessionID": "INTEGER NOT NULL",
                "Time": "TIMESTAMP NOT NULL",
                "Category": "TEXT NOT NULL",
                "Message": "TEXT",
                "Status": "TEXT",
                "Flag": "TEXT",
                "Scope": "TEXT",
                "Sector": "SMALLINT",
                "RacingNumber": "TEXT",
                "Lap": "SMALLINT"
            }
        },
        'FastF1_CircuitInfo': {
            'columns': {
                "SessionID": "INTEGER NOT NULL",
                "Feature": "TEXT NOT NULL",
                "X": "FLOAT",
                "Y": "FLOAT",
                "Number": "SMALLINT NOT NULL",
                "Letter": "TEXT NOT NULL",
                "Angle": "FLOAT",
                "Distance": "FLOAT",
                "Rotation": "FLOAT"
            }
        },
        'FastF1_TrackStatus': {
            'columns': {
                "SessionID": "INTEGER NOT NULL",
                "Time": "INTERVAL NOT NULL",
                "Status": "TEXT",
                "Message": "TEXT"
            }
        },
        'FastF1_SessionStatus': {
            'columns': {
                "SessionID": "INTEGER NOT NULL",
                "Time": "INTERVAL NOT NULL",
                "Status": "TEXT NOT NULL"
            }
        }
    }


def create_fastf1_tables_without_constraints(engine, schema='public'):
    """
    Create tables without constraints to avoid transaction issues
    Using SessionID (capital D) throughout
    """
    table_definitions = get_table_definitions()  # Use the centralized definitions
    
    # Create each table in its own transaction
    for table_name, config in table_definitions.items():
        with engine.begin() as conn:
            print(f"\nCreating table {table_name}...")
            
            # Build CREATE TABLE statement
            columns_sql = []
            for col_name, col_type in config['columns'].items():
                columns_sql.append(f'"{col_name}" {col_type}')
            
            create_sql = f"""
            CREATE TABLE IF NOT EXISTS "{schema}"."{table_name}" (
                {', '.join(columns_sql)}
            )
            """
            
            try:
                conn.execute(text(create_sql))
                print(f"  ✓ Created table {table_name}")
            except Exception as e:
                print(f"  ✗ Error creating table {table_name}: {e}")
                

def add_constraints_to_tables(engine, schema='public'):
    """
    Add constraints to tables - using SessionID throughout with proper quoting
    """
    constraints = {
        'FastF1_EventInfo': [
            ('pk_eventinfo', 'PRIMARY KEY', ['Year', 'RoundNumber', 'TestNumber']),
            ('unique_event', 'UNIQUE INDEX', '"Year", "RoundNumber", COALESCE("TestNumber", -1)')  # Quote column names
        ],
        'FastF1_Results': [
            ('pk_results', 'PRIMARY KEY', ['SessionID', 'DriverNumber']),  # Changed to SessionID
            ('unique_results', 'UNIQUE', ['SessionID', 'DriverNumber'])
        ],
        'FastF1_Weather': [
            ('pk_weather', 'PRIMARY KEY', ['SessionID', 'Time']),  # Changed to SessionID
            ('unique_weather', 'UNIQUE', ['SessionID', 'Time'])
        ],
        'FastF1_CircuitInfo': [
            ('pk_ci', 'PRIMARY KEY', ['SessionID', 'Feature', 'Number', 'Letter']),  # Changed to SessionID
            ('unique_ci', 'UNIQUE', ['SessionID', 'Feature', 'Number', 'Letter'])
        ],
        'FastF1_TrackStatus': [
            ('pk_ts', 'PRIMARY KEY', ['SessionID', 'Time']),  # Changed to SessionID
            ('unique_ts', 'UNIQUE', ['SessionID', 'Time'])
        ],
        'FastF1_SessionStatus': [
            ('pk_ss', 'PRIMARY KEY', ['SessionID', 'Time', 'Status']),  # Changed to SessionID
            ('unique_ss', 'UNIQUE', ['SessionID', 'Time', 'Status'])
        ],
        'FastF1_Laps': [
            ('unique_laps', 'UNIQUE', ['SessionID', 'Session', 'Time', 'DriverNumber'])  # Changed to SessionID
        ],
        'FastF1_CarData': [
            ('unique_cardata', 'UNIQUE', ['SessionID', 'DriverNumber', 'Time', 'Source'])  # Changed to SessionID
        ],
        'FastF1_PosData': [
            ('unique_posdata', 'UNIQUE', ['SessionID', 'DriverNumber', 'Time', 'Source'])  # Changed to SessionID
        ],
        'FastF1_RaceControlMsg': [
            ('unique_rcm', 'UNIQUE INDEX', '"SessionID", "Time", "Category", COALESCE("Message", \'\')')  # Quote column names
        ],
        'FastF1_SessionInfo': [
            ('unique_sessioninfo', 'UNIQUE', ['SessionID'])
        ]
    }
    
    # Rest of the function remains the same...
    for table_name, table_constraints in constraints.items():
        for constraint_name, constraint_type, constraint_expr in table_constraints:
            with engine.begin() as conn:
                try:
                    if constraint_type == 'PRIMARY KEY' and isinstance(constraint_expr, list):
                        # Check if table already has a primary key
                        check_pk = text("""
                            SELECT 1 FROM information_schema.table_constraints 
                            WHERE table_schema = :schema 
                            AND table_name = :table_name 
                            AND constraint_type = 'PRIMARY KEY'
                        """)
                        result = conn.execute(check_pk, {"schema": schema, "table_name": table_name})
                        
                        if not result.fetchone():
                            pk_cols = ', '.join([f'"{col}"' for col in constraint_expr])
                            conn.execute(text(f"""
                                ALTER TABLE "{schema}"."{table_name}" 
                                ADD CONSTRAINT {constraint_name} PRIMARY KEY ({pk_cols})
                            """))
                            print(f"  ✓ Added primary key to {table_name}")
                    
                    elif constraint_type == 'UNIQUE INDEX' and isinstance(constraint_expr, str) and 'COALESCE' in constraint_expr:
                        # Expression-based unique index
                        conn.execute(text(f"""
                            CREATE UNIQUE INDEX IF NOT EXISTS {constraint_name}
                            ON "{schema}"."{table_name}" ({constraint_expr})
                        """))
                        print(f"  ✓ Created unique index: {constraint_name}")
                    
                    elif constraint_type == 'UNIQUE':
                        # Regular unique constraint
                        if isinstance(constraint_expr, list):
                            cols_str = ', '.join([f'"{col}"' for col in constraint_expr])
                        else:
                            cols_str = constraint_expr
                        
                        conn.execute(text(f"""
                            ALTER TABLE "{schema}"."{table_name}"
                            ADD CONSTRAINT {constraint_name}
                            UNIQUE ({cols_str})
                        """))
                        print(f"  ✓ Created unique constraint: {constraint_name}")
                        
                except Exception as e:
                    if "already exists" not in str(e):
                        print(f"  ✗ Constraint error {constraint_name} on {table_name}: {e}")


# def create_fastf1_tables_with_proper_nulls(engine, schema='public'):
#     """
#     Create FastF1 tables with proper null handling based on actual data patterns
#     """
    
#     table_definitions = {
#         'FastF1_EventInfo': {
#             'columns': {
#                 "EventID": "INTEGER",
#                 "CountryID": "INTEGER",
#                 "CircuitID": "INTEGER",
#                 "Year": "INTEGER NOT NULL",
#                 "RoundNumber": "SMALLINT NOT NULL",
#                 "TestNumber": "SMALLINT",  # 100% null for non-test events
#                 "Country": "TEXT",
#                 "CountryCode": "TEXT",
#                 "Location": "TEXT",
#                 "Circuit": "TEXT",
#                 "OfficialEventName": "TEXT",
#                 "EventDate": "TIMESTAMP",
#                 "EventName": "TEXT",
#                 "EventFormat": "TEXT",
#                 "Session1": "TEXT",
#                 "Session1Date": "TIMESTAMP",
#                 "Session1DateUtc": "TIMESTAMP",
#                 "Session2": "TEXT",
#                 "Session2Date": "TIMESTAMP",
#                 "Session2DateUtc": "TIMESTAMP",
#                 "Session3": "TEXT",
#                 "Session3Date": "TIMESTAMP",
#                 "Session3DateUtc": "TIMESTAMP",
#                 "Session4": "TEXT",
#                 "Session4Date": "TIMESTAMP",
#                 "Session4DateUtc": "TIMESTAMP",
#                 "Session5": "TEXT",
#                 "Session5Date": "TIMESTAMP",
#                 "Session5DateUtc": "TIMESTAMP",
#                 "F1ApiSupport": "BOOLEAN"
#             },
#             'primary_key': None,  # Will use unique constraint with COALESCE
#             'unique_constraints': [
#                 ('unique_event', 'Year, RoundNumber, COALESCE(TestNumber, -1)')
#             ]
#         },
        
#         'FastF1_SessionInfo': {
#             'columns': {
#                 'SessionID': 'INTEGER PRIMARY KEY',
#                 'EventID': 'INTEGER',
#                 'SessionName': 'TEXT',
#                 'SessionType': 'TEXT',
#                 'StartDate': 'TIMESTAMP',
#                 'EndDate': 'TIMESTAMP',
#                 'GmtOffset': 'INTERVAL',
#                 'Time0': 'TIMESTAMP',
#                 'StartTime': 'INTERVAL',
#                 'ScheduledLaps': 'SMALLINT'  # 80% null - OK to be nullable
#             },
#             'unique_constraints': [('unique_sessioninfo', ['SessionID'])]
#         },
        
#         'FastF1_Results': {
#             'columns': {
#                 "SessionId": "INTEGER NOT NULL",
#                 "DriverNumber": "TEXT NOT NULL",
#                 "BroadcastName": "TEXT",
#                 "Abbreviation": "TEXT",
#                 "DriverId": "TEXT",
#                 "TeamName": "TEXT",
#                 "TeamColor": "TEXT",
#                 "TeamId": "TEXT",
#                 "FirstName": "TEXT",
#                 "LastName": "TEXT",
#                 "FullName": "TEXT",
#                 "HeadshotUrl": "TEXT",
#                 "CountryCode": "TEXT",
#                 "Position": "SMALLINT",
#                 "ClassifiedPosition": "TEXT",
#                 "GridPosition": "SMALLINT",
#                 "Q1": "INTERVAL",
#                 "Q2": "INTERVAL",
#                 "Q3": "INTERVAL",
#                 "Time": "INTERVAL",
#                 "Status": "TEXT",
#                 "Points": "FLOAT",
#                 "Laps": "SMALLINT"
#             },
#             'primary_key': ['SessionId', 'DriverNumber'],
#             'unique_constraints': [('unique_results', ['SessionId', 'DriverNumber'])]
#         },
        
#         'FastF1_Laps': {
#             'columns': {
#                 "id": "BIGSERIAL PRIMARY KEY",
#                 "SessionId": "INTEGER NOT NULL",
#                 "Session": "TEXT NOT NULL",
#                 "Time": "INTERVAL NOT NULL",
#                 "Driver": "TEXT",
#                 "DriverNumber": "TEXT NOT NULL",
#                 "LapTime": "INTERVAL",
#                 "LapNumber": "SMALLINT",
#                 "Stint": "SMALLINT",
#                 "PitOutTime": "INTERVAL",
#                 "PitInTime": "INTERVAL",
#                 "Sector1Time": "INTERVAL",
#                 "Sector2Time": "INTERVAL",
#                 "Sector3Time": "INTERVAL",
#                 "Sector1SessionTime": "INTERVAL",
#                 "Sector2SessionTime": "INTERVAL",
#                 "Sector3SessionTime": "INTERVAL",
#                 "SpeedI1": "FLOAT",
#                 "SpeedI2": "FLOAT",
#                 "SpeedFL": "FLOAT",
#                 "SpeedST": "FLOAT",
#                 "IsPersonalBest": "BOOLEAN DEFAULT FALSE",
#                 "Compound": "TEXT",
#                 "TyreLife": "SMALLINT",
#                 "FreshTyre": "BOOLEAN",
#                 "Team": "TEXT",
#                 "LapStartTime": "INTERVAL",
#                 "LapStartDate": "TIMESTAMP",
#                 "TrackStatus": "TEXT",
#                 "Position": "SMALLINT",
#                 "Deleted": "BOOLEAN DEFAULT FALSE",
#                 "DeletedReason": "TEXT DEFAULT ''",
#                 "FastF1Generated": "BOOLEAN DEFAULT FALSE",
#                 "IsAccurate": "BOOLEAN DEFAULT TRUE"
#             },
#             'unique_constraints': [('unique_laps', ['SessionId', 'Session', 'Time', 'DriverNumber'])]
#         },
        
#         'FastF1_Weather': {
#             'columns': {
#                 "SessionId": "INTEGER NOT NULL",
#                 "Time": "INTERVAL NOT NULL",
#                 "AirTemp": "FLOAT",
#                 "Humidity": "FLOAT",
#                 "Pressure": "FLOAT",
#                 "Rainfall": "BOOLEAN",
#                 "TrackTemp": "FLOAT",
#                 "WindDirection": "SMALLINT",
#                 "WindSpeed": "FLOAT"
#             },
#             'primary_key': ['SessionId', 'Time'],
#             'unique_constraints': [('unique_weather', ['SessionId', 'Time'])]
#         },
        
#         'FastF1_CarData': {
#             'columns': {
#                 "id": "BIGSERIAL PRIMARY KEY",
#                 "SessionId": "INTEGER NOT NULL",
#                 "DriverNumber": "TEXT NOT NULL",
#                 "Date": "TIMESTAMP",
#                 "SessionTime": "INTERVAL",
#                 "Time": "INTERVAL NOT NULL",
#                 "Source": "TEXT NOT NULL",
#                 "RPM": "FLOAT",
#                 "Speed": "FLOAT",
#                 "nGear": "SMALLINT",
#                 "Throttle": "FLOAT",
#                 "Brake": "BOOLEAN",
#                 "DRS": "SMALLINT",
#                 "DriverAhead": "TEXT",
#                 "DistanceToDriverAhead": "FLOAT",
#                 "Distance": "FLOAT",
#                 "RelativeDistance": "FLOAT"
#             },
#             'unique_constraints': [('unique_cardata', ['SessionId', 'DriverNumber', 'Time', 'Source'])]
#         },
        
#         'FastF1_PosData': {
#             'columns': {
#                 "id": "BIGSERIAL PRIMARY KEY",
#                 "SessionId": "INTEGER NOT NULL",
#                 "DriverNumber": "TEXT NOT NULL",
#                 "Date": "TIMESTAMP",
#                 "SessionTime": "INTERVAL",
#                 "Time": "INTERVAL NOT NULL",
#                 "Source": "TEXT NOT NULL",
#                 "Status": "TEXT",
#                 "X": "FLOAT",
#                 "Y": "FLOAT",
#                 "Z": "FLOAT"
#             },
#             'unique_constraints': [('unique_posdata', ['SessionId', 'DriverNumber', 'Time', 'Source'])]
#         },
        
#         'FastF1_RaceControlMsg': {
#             'columns': {
#                 "id": "BIGSERIAL PRIMARY KEY",
#                 "SessionId": "INTEGER NOT NULL",
#                 "Time": "TIMESTAMP NOT NULL",
#                 "Category": "TEXT NOT NULL",
#                 "Message": "TEXT",
#                 "Status": "TEXT",
#                 "Flag": "TEXT",
#                 "Scope": "TEXT",
#                 "Sector": "SMALLINT",
#                 "RacingNumber": "TEXT",
#                 "Lap": "SMALLINT"
#             },
#             'unique_constraints': [
#                 ('unique_rcm', 'SessionId, Time, Category, COALESCE(Message, \'\')')
#             ]
#         },
        
#         'FastF1_CircuitInfo': {
#             'columns': {
#                 "SessionId": "INTEGER NOT NULL",
#                 "Feature": "TEXT NOT NULL",
#                 "X": "FLOAT",
#                 "Y": "FLOAT",
#                 "Number": "SMALLINT NOT NULL",
#                 "Letter": "TEXT NOT NULL",
#                 "Angle": "FLOAT",
#                 "Distance": "FLOAT",
#                 "Rotation": "FLOAT"
#             },
#             'primary_key': ['SessionId', 'Feature', 'Number', 'Letter'],
#             'unique_constraints': [('unique_ci', ['SessionId', 'Feature', 'Number', 'Letter'])]
#         },
        
#         'FastF1_TrackStatus': {
#             'columns': {
#                 "SessionId": "INTEGER NOT NULL",
#                 "Time": "INTERVAL NOT NULL",
#                 "Status": "TEXT",
#                 "Message": "TEXT"
#             },
#             'primary_key': ['SessionId', 'Time'],
#             'unique_constraints': [('unique_ts', ['SessionId', 'Time'])]
#         },
        
#         'FastF1_SessionStatus': {
#             'columns': {
#                 "SessionId": "INTEGER NOT NULL",
#                 "Time": "INTERVAL NOT NULL",
#                 "Status": "TEXT NOT NULL"
#             },
#             'primary_key': ['SessionId', 'Time', 'Status'],
#             'unique_constraints': [('unique_ss', ['SessionId', 'Time', 'Status'])]
#         }
#     }
    
#     # Create tables implementation remains the same...
#     with engine.begin() as conn:
#         # Create tables
#         for table_name, config in table_definitions.items():
#             print(f"\nCreating table {table_name}...")
            
#             # Build CREATE TABLE statement
#             columns_sql = []
#             for col_name, col_type in config['columns'].items():
#                 columns_sql.append(f'"{col_name}" {col_type}')
            
#             # Add composite primary key if specified
#             if config.get('primary_key') and not any('PRIMARY KEY' in col for col in columns_sql):
#                 pk_cols = ', '.join([f'"{col}"' for col in config['primary_key']])
#                 columns_sql.append(f'PRIMARY KEY ({pk_cols})')
            
#             create_sql = f"""
#             CREATE TABLE IF NOT EXISTS "{schema}"."{table_name}" (
#                 {', '.join(columns_sql)}
#             )
#             """
            
#             try:
#                 conn.execute(text(create_sql))
#                 print(f"  ✓ Created table {table_name}")
#             except Exception as e:
#                 print(f"  ✗ Error creating table {table_name}: {e}")
        
#         # Add unique constraints
#         for table_name, config in table_definitions.items():
#             for constraint_name, constraint_expr in config.get('unique_constraints', []):
#                 try:
#                     if isinstance(constraint_expr, str) and 'COALESCE' in constraint_expr:
#                         # Expression-based unique index
#                         conn.execute(text(f"""
#                             CREATE UNIQUE INDEX IF NOT EXISTS {constraint_name}
#                             ON "{schema}"."{table_name}" ({constraint_expr})
#                         """))
#                     else:
#                         # Regular column-based unique constraint
#                         if isinstance(constraint_expr, list):
#                             cols = constraint_expr
#                         else:
#                             cols = [c.strip() for c in constraint_expr.split(',')]
                        
#                         cols_str = ', '.join([f'"{col}"' for col in cols])
                        
#                         # Check if any columns are nullable
#                         nullable_cols = []
#                         for col in cols:
#                             for col_name, col_type in config['columns'].items():
#                                 if col_name == col and 'NOT NULL' not in col_type:
#                                     nullable_cols.append(col)
                        
#                         if nullable_cols:
#                             # Use partial unique index
#                             where_clause = ' AND '.join([f'"{col}" IS NOT NULL' for col in nullable_cols])
#                             conn.execute(text(f"""
#                                 CREATE UNIQUE INDEX IF NOT EXISTS {constraint_name}
#                                 ON "{schema}"."{table_name}" ({cols_str})
#                                 WHERE {where_clause}
#                             """))
#                         else:
#                             # Regular unique constraint
#                             conn.execute(text(f"""
#                                 ALTER TABLE "{schema}"."{table_name}"
#                                 ADD CONSTRAINT {constraint_name}
#                                 UNIQUE ({cols_str})
#                             """))
                    
#                     print(f"  ✓ Created unique constraint: {constraint_name}")
#                 except Exception as e:
#                     print(f"  ✗ Constraint error {constraint_name}: {e}")


# def create_fastf1_tables(engine, schema='public'):
#     """
#     Create all FastF1 tables with proper data types, keys, and constraints
#     """
    
#     # Table definitions with data types
#     table_definitions = {
#         'FastF1_EventInfo': {
#             'columns': {
#                 "EventID": "INTEGER",
#                 "CountryID": "INTEGER",
#                 "CircuitID": "INTEGER",
#                 "Year": "INTEGER NOT NULL",
#                 "RoundNumber": "SMALLINT NOT NULL",
#                 "TestNumber": "SMALLINT",
#                 "Country": "TEXT",
#                 "CountryCode": "TEXT",
#                 "Location": "TEXT",
#                 "Circuit": "TEXT",
#                 "OfficialEventName": "TEXT",
#                 "EventDate": "TIMESTAMP",
#                 "EventName": "TEXT",
#                 "EventFormat": "TEXT",
#                 "Session1": "TEXT",
#                 "Session1Date": "TIMESTAMP",
#                 "Session1DateUtc": "TIMESTAMP",
#                 "Session2": "TEXT",
#                 "Session2Date": "TIMESTAMP",
#                 "Session2DateUtc": "TIMESTAMP",
#                 "Session3": "TEXT",
#                 "Session3Date": "TIMESTAMP",
#                 "Session3DateUtc": "TIMESTAMP",
#                 "Session4": "TEXT",
#                 "Session4Date": "TIMESTAMP",
#                 "Session4DateUtc": "TIMESTAMP",
#                 "Session5": "TEXT",
#                 "Session5Date": "TIMESTAMP",
#                 "Session5DateUtc": "TIMESTAMP",
#                 "F1ApiSupport": "BOOLEAN"
#             },
#             'primary_key': ['Year', 'RoundNumber', 'TestNumber'],
#             'unique_constraints': [('unique_event', ['Year', 'RoundNumber', 'TestNumber'])]
#         },
        
#         'FastF1_SessionInfo': {
#             'columns': {
#                 'SessionID': 'INTEGER PRIMARY KEY',
#                 'EventID': 'INTEGER',
#                 'SessionName': 'TEXT',
#                 'SessionType': 'TEXT',
#                 'StartDate': 'TIMESTAMP',
#                 'EndDate': 'TIMESTAMP',
#                 'GmtOffset': 'INTERVAL',
#                 'Time0': 'TIMESTAMP',
#                 'StartTime': 'INTERVAL',
#                 'ScheduledLaps': 'SMALLINT'
#             },
#             'unique_constraints': [('unique_sessioninfo', ['SessionID'])]
#         },
        
#         'FastF1_Results': {
#             'columns': {
#                 "SessionId": "INTEGER NOT NULL",
#                 "DriverNumber": "TEXT NOT NULL",
#                 "BroadcastName": "TEXT",
#                 "Abbreviation": "TEXT",
#                 "DriverId": "TEXT",
#                 "TeamName": "TEXT",
#                 "TeamColor": "TEXT",
#                 "TeamId": "TEXT",
#                 "FirstName": "TEXT",
#                 "LastName": "TEXT",
#                 "FullName": "TEXT",
#                 "HeadshotUrl": "TEXT",
#                 "CountryCode": "TEXT",
#                 "Position": "SMALLINT",
#                 "ClassifiedPosition": "TEXT",
#                 "GridPosition": "SMALLINT",
#                 "Q1": "INTERVAL",
#                 "Q2": "INTERVAL",
#                 "Q3": "INTERVAL",
#                 "Time": "INTERVAL",
#                 "Status": "TEXT",
#                 "Points": "FLOAT",
#                 "Laps": "SMALLINT"
#             },
#             'primary_key': ['SessionId', 'DriverNumber'],
#             'unique_constraints': [('unique_results', ['SessionId', 'DriverNumber'])]
#         },
        
#         'FastF1_Laps': {
#             'columns': {
#                 "id": "BIGSERIAL PRIMARY KEY",
#                 "SessionId": "INTEGER NOT NULL",
#                 "Session": "TEXT",
#                 "Time": "INTERVAL",
#                 "Driver": "TEXT",
#                 "DriverNumber": "TEXT",
#                 "LapTime": "INTERVAL",
#                 "LapNumber": "SMALLINT",
#                 "Stint": "SMALLINT",
#                 "PitOutTime": "INTERVAL",
#                 "PitInTime": "INTERVAL",
#                 "Sector1Time": "INTERVAL",
#                 "Sector2Time": "INTERVAL",
#                 "Sector3Time": "INTERVAL",
#                 "Sector1SessionTime": "INTERVAL",
#                 "Sector2SessionTime": "INTERVAL",
#                 "Sector3SessionTime": "INTERVAL",
#                 "SpeedI1": "FLOAT",
#                 "SpeedI2": "FLOAT",
#                 "SpeedFL": "FLOAT",
#                 "SpeedST": "FLOAT",
#                 "IsPersonalBest": "BOOLEAN",
#                 "Compound": "TEXT",
#                 "TyreLife": "SMALLINT",
#                 "FreshTyre": "BOOLEAN",
#                 "Team": "TEXT",
#                 "LapStartTime": "INTERVAL",
#                 "LapStartDate": "TIMESTAMP",
#                 "TrackStatus": "TEXT",
#                 "Position": "SMALLINT",
#                 "Deleted": "BOOLEAN",
#                 "DeletedReason": "TEXT",
#                 "FastF1Generated": "BOOLEAN",
#                 "IsAccurate": "BOOLEAN"
#             },
#             'unique_constraints': [('unique_laps', ['SessionId', 'Session', 'Time', 'DriverNumber'])]
#         },
        
#         'FastF1_Weather': {
#             'columns': {
#                 "SessionId": "INTEGER NOT NULL",
#                 "Time": "INTERVAL NOT NULL",
#                 "AirTemp": "FLOAT",
#                 "Humidity": "FLOAT",
#                 "Pressure": "FLOAT",
#                 "Rainfall": "BOOLEAN",
#                 "TrackTemp": "FLOAT",
#                 "WindDirection": "SMALLINT",
#                 "WindSpeed": "FLOAT"
#             },
#             'primary_key': ['SessionId', 'Time'],
#             'unique_constraints': [('unique_weather', ['SessionId', 'Time'])]
#         },
        
#         'FastF1_Telemetry': {
#             'columns': {
#                 "id": "BIGSERIAL PRIMARY KEY",
#                 "SessionId": "INTEGER NOT NULL",
#                 "DriverNumber": "TEXT NOT NULL",
#                 "Date": "TIMESTAMP",
#                 "SessionTime": "INTERVAL",
#                 "DriverAhead": "TEXT",
#                 "DistanceToDriverAhead": "FLOAT",
#                 "Time": "INTERVAL NOT NULL",
#                 "RPM": "FLOAT",
#                 "Speed": "FLOAT",
#                 "nGear": "SMALLINT",
#                 "Throttle": "FLOAT",
#                 "Brake": "BOOLEAN",
#                 "DRS": "SMALLINT",
#                 "Source": "TEXT NOT NULL",
#                 "Distance": "FLOAT",
#                 "RelativeDistance": "FLOAT",
#                 "Status": "TEXT",
#                 "X": "FLOAT",
#                 "Y": "FLOAT",
#                 "Z": "FLOAT"
#             },
#             'unique_constraints': [('unique_telemetry', ['SessionId', 'DriverNumber', 'Time', 'Source'])]
#         },
        
#         'FastF1_RaceControlMsg': {
#             'columns': {
#                 "SessionId": "INTEGER NOT NULL",
#                 "Time": "TIMESTAMP NOT NULL",
#                 "Category": "TEXT NOT NULL",
#                 "Message": "TEXT",
#                 "Status": "TEXT NOT NULL",
#                 "Flag": "TEXT",
#                 "Scope": "TEXT",
#                 "Sector": "SMALLINT",
#                 "RacingNumber": "TEXT",
#                 "Lap": "SMALLINT"
#             },
#             'primary_key': ['SessionId', 'Time', 'Category', 'Status', 'RacingNumber', 'Sector'],
#             'unique_constraints': [('unique_rcm', ['SessionId', 'Time', 'Category', 'Status', 'RacingNumber', 'Sector'])]
#         },
        
#         'FastF1_CircuitInfo': {
#             'columns': {
#                 "SessionId": "INTEGER NOT NULL",
#                 "Feature": "TEXT NOT NULL",
#                 "X": "FLOAT",
#                 "Y": "FLOAT",
#                 "Number": "SMALLINT NOT NULL",
#                 "Letter": "TEXT NOT NULL",
#                 "Angle": "FLOAT",
#                 "Distance": "FLOAT",
#                 "Rotation": "FLOAT"
#             },
#             'primary_key': ['SessionId', 'Feature', 'Number', 'Letter'],
#             'unique_constraints': [('unique_ci', ['SessionId', 'Feature', 'Number', 'Letter'])]
#         },
        
#         'FastF1_TrackStatus': {
#             'columns': {
#                 "SessionId": "INTEGER NOT NULL",
#                 "Time": "INTERVAL NOT NULL",
#                 "Status": "TEXT",
#                 "Message": "TEXT"
#             },
#             'primary_key': ['SessionId', 'Time'],
#             'unique_constraints': [('unique_ts', ['SessionId', 'Time'])]
#         },
        
#         'FastF1_SessionStatus': {
#             'columns': {
#                 "SessionId": "INTEGER NOT NULL",
#                 "Time": "INTERVAL NOT NULL",
#                 "Status": "TEXT NOT NULL"
#             },
#             'primary_key': ['SessionId', 'Time', 'Status'],
#             'unique_constraints': [('unique_ss', ['SessionId', 'Time', 'Status'])]
#         }
#     }
    
#     with engine.begin() as conn:
#         # Create tables
#         for table_name, config in table_definitions.items():
#             print(f"\nCreating table {table_name}...")
            
#             # Build CREATE TABLE statement
#             columns_sql = []
#             for col_name, col_type in config['columns'].items():
#                 columns_sql.append(f'"{col_name}" {col_type}')
            
#             # Add primary key constraint if not using SERIAL
#             if 'primary_key' in config and 'id' not in config['primary_key']:
#                 pk_cols = ', '.join([f'"{col}"' for col in config['primary_key']])
#                 columns_sql.append(f'PRIMARY KEY ({pk_cols})')
            
#             create_sql = f"""
#             CREATE TABLE IF NOT EXISTS "{schema}"."{table_name}" (
#                 {', '.join(columns_sql)}
#             )
#             """
            
#             try:
#                 conn.execute(text(create_sql))
#                 print(f"  ✓ Created table {table_name}")
#             except Exception as e:
#                 print(f"  ✗ Error creating table {table_name}: {e}")
        
#         # Add unique constraints
#         for table_name, config in table_definitions.items():
#             for constraint_name, constraint_cols in config.get('unique_constraints', []):
#                 try:
#                     cols_str = ', '.join([f'"{col}"' for col in constraint_cols])
#                     # Use partial unique index for nullable columns
#                     where_clause = ' AND '.join([f'"{col}" IS NOT NULL' for col in constraint_cols])
#                     conn.execute(text(f"""
#                         CREATE UNIQUE INDEX IF NOT EXISTS {constraint_name}
#                         ON "{schema}"."{table_name}" ({cols_str})
#                         WHERE {where_clause}
#                     """))
#                     print(f"  ✓ Created unique constraint: {constraint_name}")
#                 except Exception as e:
#                     print(f"  ✗ Constraint error {constraint_name}: {e}")


def create_indexes_and_foreign_keys(engine, schema='public'):
    """
    Create all indexes and foreign key relationships with SessionID (uppercase D)
    """
    
    # Create indexes - all using SessionID now
    indexes = [
        # EventInfo indexes
        ('idx_eventinfo_year', 'FastF1_EventInfo', ['Year']),
        ('idx_eventinfo_format', 'FastF1_EventInfo', ['EventFormat']),
        ('idx_eventinfo_circuit', 'FastF1_EventInfo', ['CircuitID']),
        
        # SessionInfo indexes
        ('idx_sessioninfo_event', 'FastF1_SessionInfo', ['EventID']),
        ('idx_sessioninfo_type', 'FastF1_SessionInfo', ['SessionType']),
        
        # Results indexes
        ('idx_results_session', 'FastF1_Results', ['SessionID']),  # Changed
        ('idx_results_driver', 'FastF1_Results', ['DriverNumber']),
        ('idx_results_team', 'FastF1_Results', ['TeamID']),  # Also changed to TeamID
        ('idx_results_position', 'FastF1_Results', ['Position']),
        
        # Laps indexes
        ('idx_laps_session_driver', 'FastF1_Laps', ['SessionID', 'DriverNumber']),  # Changed
        ('idx_laps_compound', 'FastF1_Laps', ['Compound']),
        ('idx_laps_stint', 'FastF1_Laps', ['SessionID', 'DriverNumber', 'Stint']),  # Changed
        ('idx_laps_valid', 'FastF1_Laps', ['SessionID', 'DriverNumber'], 'WHERE "Deleted" = FALSE'),  # Changed
        
        # Weather indexes
        ('idx_weather_session', 'FastF1_Weather', ['SessionID']),  # Changed
        ('idx_weather_rain', 'FastF1_Weather', ['SessionID'], 'WHERE "Rainfall" = TRUE'),  # Changed
        
        # CarData indexes
        ('idx_cardata_session_driver', 'FastF1_CarData', ['SessionID', 'DriverNumber']),  # Changed
        ('idx_cardata_time', 'FastF1_CarData', ['SessionID', 'DriverNumber', 'Time']),  # Changed
        ('idx_cardata_drs', 'FastF1_CarData', ['SessionID', 'DriverNumber'], 'WHERE "DRS" > 0'),  # Changed
        ('idx_cardata_source', 'FastF1_CarData', ['Source']),
        
        # PosData indexes
        ('idx_posdata_session_driver', 'FastF1_PosData', ['SessionID', 'DriverNumber']),  # Changed
        ('idx_posdata_time', 'FastF1_PosData', ['SessionID', 'DriverNumber', 'Time']),  # Changed
        ('idx_posdata_spatial', 'FastF1_PosData', ['SessionID', 'X', 'Y']),  # Changed
        ('idx_posdata_source', 'FastF1_PosData', ['Source']),
        
        # Race control indexes
        ('idx_rcm_session', 'FastF1_RaceControlMsg', ['SessionID']),  # Changed
        ('idx_rcm_category', 'FastF1_RaceControlMsg', ['Category']),
        ('idx_rcm_flag', 'FastF1_RaceControlMsg', ['Flag'], 'WHERE "Flag" IS NOT NULL'),
        
        # Circuit info indexes
        ('idx_ci_session', 'FastF1_CircuitInfo', ['SessionID']),  # Changed
        ('idx_ci_feature', 'FastF1_CircuitInfo', ['Feature']),
        
        # Track/Session status indexes
        ('idx_ts_session', 'FastF1_TrackStatus', ['SessionID']),  # Changed
        ('idx_ss_session', 'FastF1_SessionStatus', ['SessionID']),  # Changed
    ]
    
    # Covering indexes
    covering_indexes = [
        # Results covering index for quali analysis
        ('idx_results_quali_covering', 'FastF1_Results', 
         ['SessionID', 'DriverNumber'],  # Changed
         ['Q1', 'Q2', 'Q3', 'Position', 'GridPosition']),
        
        # Laps covering index for lap time analysis
        ('idx_laps_analysis_covering', 'FastF1_Laps',
         ['SessionID', 'DriverNumber', 'LapNumber'],  # Changed
         ['LapTime', 'Sector1Time', 'Sector2Time', 'Sector3Time', 'Compound', 'TyreLife']),
        
        # CarData covering index for telemetry analysis
        ('idx_cardata_covering', 'FastF1_CarData',
         ['SessionID', 'DriverNumber', 'Time'],  # Changed
         ['Speed', 'RPM', 'nGear', 'Throttle', 'Brake', 'DRS']),
        
        # PosData covering index for position tracking
        ('idx_posdata_covering', 'FastF1_PosData',
         ['SessionID', 'DriverNumber', 'Time'],  # Changed
         ['X', 'Y', 'Z', 'Status']),
    ]
    
    # First, check what the actual column name is in SessionInfo
    with engine.connect() as conn:
        check_column_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = :schema 
            AND table_name = 'FastF1_SessionInfo'
            AND column_name IN ('SessionID', 'SessionId')
        """)
        result = conn.execute(check_column_query, {"schema": schema})
        session_id_column = result.scalar()
        
        if not session_id_column:
            print("⚠️ Warning: No SessionID/SessionId column found in FastF1_SessionInfo")
            session_id_column = 'SessionID'  # Default
        else:
            print(f"✓ Found SessionInfo primary key column: {session_id_column}")
    
    with engine.begin() as conn:
        # Create regular indexes
        for index_info in indexes:
            if len(index_info) == 3:
                idx_name, table_name, columns = index_info
                where_clause = ""
            else:
                idx_name, table_name, columns, where_clause = index_info
            
            try:
                cols_str = ', '.join([f'"{col}"' for col in columns])
                sql = f"""
                    CREATE INDEX IF NOT EXISTS {idx_name}
                    ON "{schema}"."{table_name}" ({cols_str})
                    {where_clause}
                """
                conn.execute(text(sql))
                print(f"✓ Created index: {idx_name}")
            except Exception as e:
                print(f"✗ Index error {idx_name}: {e}")
        
        # Create covering indexes
        for idx_name, table_name, key_cols, include_cols in covering_indexes:
            try:
                key_cols_str = ', '.join([f'"{col}"' for col in key_cols])
                include_cols_str = ', '.join([f'"{col}"' for col in include_cols])
                conn.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS {idx_name}
                    ON "{schema}"."{table_name}" ({key_cols_str})
                    INCLUDE ({include_cols_str})
                """))
                print(f"✓ Created covering index: {idx_name}")
            except Exception as e:
                print(f"✗ Covering index error {idx_name}: {e}")
    
    # Create foreign keys in a separate transaction
    with engine.begin() as conn:
        # All foreign keys now use SessionID consistently
        foreign_keys = [
            ('FastF1_Results', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
            ('FastF1_Laps', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
            ('FastF1_Weather', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
            ('FastF1_CarData', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
            ('FastF1_PosData', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
            ('FastF1_RaceControlMsg', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
            ('FastF1_CircuitInfo', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
            ('FastF1_TrackStatus', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
            ('FastF1_SessionStatus', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
        ]
        
        for child_table, parent_table, child_col, parent_col in foreign_keys:
            fk_name = f"fk_{child_table.lower()}_{child_col.lower()}"
            try:
                conn.execute(text(f"""
                    ALTER TABLE "{schema}"."{child_table}"
                    ADD CONSTRAINT {fk_name}
                    FOREIGN KEY ("{child_col}")
                    REFERENCES "{schema}"."{parent_table}" ("{parent_col}")
                    ON DELETE CASCADE
                """))
                print(f"✓ Added FK: {child_table}.{child_col} -> {parent_table}.{parent_col}")
            except Exception as e:
                if "already exists" not in str(e):
                    print(f"✗ FK error {fk_name}: {e}")
                    

def get_dtype_mappings():
    """
    Return the dtype mappings for use with pandas to_sql
    """
    return {
        'FastF1_EventInfo': {
            "EventID": postgresql.INTEGER(),
            "CountryID": postgresql.INTEGER(),
            "CircuitID": postgresql.INTEGER(),
            "Year": postgresql.INTEGER(),
            "RoundNumber": postgresql.SMALLINT(),
            "TestNumber": postgresql.SMALLINT(),
            "Country": postgresql.TEXT(),
            "CountryCode": postgresql.TEXT(),
            "Location": postgresql.TEXT(),
            "Circuit": postgresql.TEXT(),
            "OfficialEventName": postgresql.TEXT(),
            "EventDate": postgresql.TIMESTAMP(),
            "EventName": postgresql.TEXT(),
            "EventFormat": postgresql.TEXT(),
            **{f"Session{i}": postgresql.TEXT() for i in range(1, 6)},
            **{f"Session{i}Date": postgresql.TIMESTAMP() for i in range(1, 6)},
            **{f"Session{i}DateUtc": postgresql.TIMESTAMP() for i in range(1, 6)},
               "F1ApiSupport": postgresql.BOOLEAN()
        },
        'FastF1_SessionInfo': {
            'SessionID': postgresql.INTEGER(),
            'EventID': postgresql.INTEGER(),
            'SessionName': postgresql.TEXT(),
            'SessionType': postgresql.TEXT(),
            'StartDate': postgresql.TIMESTAMP(),
            'EndDate': postgresql.TIMESTAMP(),
            'GmtOffset': postgresql.INTERVAL(),
            'Time0': postgresql.TIMESTAMP(),
            'StartTime': postgresql.INTERVAL(),
            'ScheduledLaps': postgresql.SMALLINT()
        },
        'FastF1_Results': {
            "SessionId": postgresql.INTEGER(),
            "DriverNumber": postgresql.TEXT(),
            "BroadcastName": postgresql.TEXT(),
            "Abbreviation": postgresql.TEXT(),
            "DriverId": postgresql.TEXT(),
            "TeamName": postgresql.TEXT(),
            "TeamColor": postgresql.TEXT(),
            "TeamId": postgresql.TEXT(),
            "FirstName": postgresql.TEXT(),
            "LastName": postgresql.TEXT(),
            "FullName": postgresql.TEXT(),
            "HeadshotUrl": postgresql.TEXT(),
            "CountryCode": postgresql.TEXT(),
            "Position": postgresql.SMALLINT(),
            "ClassifiedPosition": postgresql.TEXT(),
            "GridPosition": postgresql.SMALLINT(),
            "Q1": postgresql.INTERVAL(),
            "Q2": postgresql.INTERVAL(),
            "Q3": postgresql.INTERVAL(),
            "Time": postgresql.INTERVAL(),
            "Status": postgresql.TEXT(),
            "Points": postgresql.FLOAT(),
            "Laps": postgresql.SMALLINT()
        },
        'FastF1_Laps': {
            "SessionId": postgresql.INTEGER(),
            "Session": postgresql.TEXT(),
            "Time": postgresql.INTERVAL(),
            "Driver": postgresql.TEXT(),
            "DriverNumber": postgresql.TEXT(),
            "LapTime": postgresql.INTERVAL(),
            "LapNumber": postgresql.SMALLINT(),
            "Stint": postgresql.SMALLINT(),
            "PitOutTime": postgresql.INTERVAL(),
            "PitInTime": postgresql.INTERVAL(),
            "Sector1Time": postgresql.INTERVAL(),
            "Sector2Time": postgresql.INTERVAL(),
            "Sector3Time": postgresql.INTERVAL(),
            "Sector1SessionTime": postgresql.INTERVAL(),
            "Sector2SessionTime": postgresql.INTERVAL(),
            "Sector3SessionTime": postgresql.INTERVAL(),
            "SpeedI1": postgresql.FLOAT(),
            "SpeedI2": postgresql.FLOAT(),
            "SpeedFL": postgresql.FLOAT(),
            "SpeedST": postgresql.FLOAT(),
            "IsPersonalBest": postgresql.BOOLEAN(),
            "Compound": postgresql.TEXT(),
            "TyreLife": postgresql.SMALLINT(),
            "FreshTyre": postgresql.BOOLEAN(),
            "Team": postgresql.TEXT(),
            "LapStartTime": postgresql.INTERVAL(),
            "LapStartDate": postgresql.TIMESTAMP(),
            "TrackStatus": postgresql.TEXT(),
            "Position": postgresql.SMALLINT(),
            "Deleted": postgresql.BOOLEAN(),
            "DeletedReason": postgresql.TEXT(),
            "FastF1Generated": postgresql.BOOLEAN(),
            "IsAccurate": postgresql.BOOLEAN()
        },
        'FastF1_Weather': {
            "SessionId": postgresql.INTEGER(),
            "Time": postgresql.INTERVAL(),
            "AirTemp": postgresql.FLOAT(),
            "Humidity": postgresql.FLOAT(),
            "Pressure": postgresql.FLOAT(),
            "Rainfall": postgresql.BOOLEAN(),
            "TrackTemp": postgresql.FLOAT(),
            "WindDirection": postgresql.SMALLINT(),
            "WindSpeed": postgresql.FLOAT()
        },
        'FastF1_CarData': {
            "SessionId": postgresql.INTEGER(),
            "DriverNumber": postgresql.TEXT(),
            "Date": postgresql.TIMESTAMP(),
            "SessionTime": postgresql.INTERVAL(),
            "Time": postgresql.INTERVAL(),
            "Source": postgresql.TEXT(),
            "RPM": postgresql.FLOAT(),
            "Speed": postgresql.FLOAT(),
            "nGear": postgresql.SMALLINT(),
            "Throttle": postgresql.FLOAT(),
            "Brake": postgresql.BOOLEAN(),
            "DRS": postgresql.SMALLINT(),
            "DriverAhead": postgresql.TEXT(),
            "DistanceToDriverAhead": postgresql.FLOAT(),
            "Distance": postgresql.FLOAT(),
            "RelativeDistance": postgresql.FLOAT()
        },
        'FastF1_PosData': {
            "SessionId": postgresql.INTEGER(),
            "DriverNumber": postgresql.TEXT(),
            "Date": postgresql.TIMESTAMP(),
            "SessionTime": postgresql.INTERVAL(),
            "Time": postgresql.INTERVAL(),
            "Source": postgresql.TEXT(),
            "Status": postgresql.TEXT(),
            "X": postgresql.FLOAT(),
            "Y": postgresql.FLOAT(),
            "Z": postgresql.FLOAT()
        },
        'FastF1_RaceControlMsg': {
            "SessionId": postgresql.INTEGER(),
            "Time": postgresql.TIMESTAMP(),
            "Category": postgresql.TEXT(),
            "Message": postgresql.TEXT(),
            "Status": postgresql.TEXT(),
            "Flag": postgresql.TEXT(),
            "Scope": postgresql.TEXT(),
            "Sector": postgresql.SMALLINT(),
            "RacingNumber": postgresql.TEXT(),
            "Lap": postgresql.SMALLINT()
        },
        'FastF1_CircuitInfo': {
            "SessionId": postgresql.INTEGER(),
            "Feature": postgresql.TEXT(),
            "X": postgresql.FLOAT(),
            "Y": postgresql.FLOAT(),
            "Number": postgresql.SMALLINT(),
            "Letter": postgresql.TEXT(),
            "Angle": postgresql.FLOAT(),
            "Distance": postgresql.FLOAT(),
            "Rotation": postgresql.FLOAT()
        },
        'FastF1_TrackStatus': {
            "SessionId": postgresql.INTEGER(),
            "Time": postgresql.INTERVAL(),
            "Status": postgresql.TEXT(),
            "Message": postgresql.TEXT()
        },
        'FastF1_SessionStatus': {
            "SessionId": postgresql.INTEGER(),
            "Time": postgresql.INTERVAL(),
            "Status": postgresql.TEXT()
        }
    }

# # Main function to set up everything
# def setup_fastf1_database(engine, schema='public'):
#     """
#     Complete setup of FastF1 database tables
#     """
#     print("Setting up FastF1 database schema...")
    
#     # Create tables
#     create_fastf1_tables(engine, schema)
    
#     # Create indexes and foreign keys
#     create_indexes_and_foreign_keys(engine, schema)
    
#     # Analyze tables
#     analyze_tables(engine, schema)
    
#     print("\nDatabase setup complete!")
    
#     return get_dtype_mappings()

def analyze_tables(engine, schema='public'):
    """
    Analyze all tables for query optimization
    """
    tables = [
        'FastF1_EventInfo', 'FastF1_SessionInfo', 'FastF1_Results',
        'FastF1_Laps', 'FastF1_Weather', 'FastF1_CarData', 'FastF1_PosData',
        'FastF1_RaceControlMsg', 'FastF1_CircuitInfo',
        'FastF1_TrackStatus', 'FastF1_SessionStatus'
    ]
    
    with engine.begin() as conn:
        for table in tables:
            try:
                conn.execute(text(f'ANALYZE "{schema}"."{table}"'))
                print(f"✓ Analyzed {table}")
            except Exception as e:
                print(f"✗ Error analyzing {table}: {e}")

def inspect_table_constraints_and_indexes(engine, table_name, schema='public'):
    """
    Show all constraints and indexes for a table
    """
    with engine.connect() as conn:
        # Get constraints
        constraints_query = text("""
            SELECT 
                pc.conname as constraint_name,
                CASE pc.contype 
                    WHEN 'p' THEN 'PRIMARY KEY'
                    WHEN 'f' THEN 'FOREIGN KEY'
                    WHEN 'u' THEN 'UNIQUE'
                    WHEN 'c' THEN 'CHECK'
                END as constraint_type
            FROM pg_constraint pc
            JOIN pg_class c ON c.oid = pc.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = :schema
            AND c.relname = :table_name
            ORDER BY pc.contype, pc.conname
        """)
        
        # Get indexes
        indexes_query = text("""
            SELECT 
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = :schema
            AND tablename = :table_name
            ORDER BY indexname
        """)
        
        print(f"\nConstraints for {table_name}:")
        try:
            constraints = conn.execute(constraints_query, {"schema": schema, "table_name": table_name})
            constraint_count = 0
            for name, type_ in constraints:
                print(f"  - {name} ({type_})")
                constraint_count += 1
            if constraint_count == 0:
                print("  - No constraints found")
        except Exception as e:
            print(f"  - Error getting constraints: {e}")
        
        print(f"\nIndexes for {table_name}:")
        try:
            indexes = conn.execute(indexes_query, {"schema": schema, "table_name": table_name})
            index_count = 0
            for name, definition in indexes:
                print(f"  - {name}")
                index_count += 1
            if index_count == 0:
                print("  - No indexes found")
        except Exception as e:
            print(f"  - Error getting indexes: {e}")
            
            
def verify_table_structure(engine, schema='public'):
    """
    Verify that all tables were created correctly
    """
    tables_to_check = [
        'FastF1_EventInfo', 'FastF1_SessionInfo', 'FastF1_Results',
        'FastF1_Laps', 'FastF1_Weather', 'FastF1_CarData', 'FastF1_PosData',
        'FastF1_RaceControlMsg', 'FastF1_CircuitInfo',
        'FastF1_TrackStatus', 'FastF1_SessionStatus'
    ]
    
    with engine.connect() as conn:
        for table_name in tables_to_check:
            print(f"\n{table_name}:")
            
            # Check columns
            columns_query = text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = :schema
                AND table_name = :table_name
                ORDER BY ordinal_position
            """)
            
            columns = conn.execute(columns_query, {"schema": schema, "table_name": table_name})
            for col_name, data_type, is_nullable in columns:
                print(f"  - {col_name}: {data_type} {'(nullable)' if is_nullable == 'YES' else '(NOT NULL)'}")
            
            # Check primary key
            pk_query = text("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_schema = :schema
                AND tc.table_name = :table_name
                AND tc.constraint_type = 'PRIMARY KEY'
                ORDER BY kcu.ordinal_position
            """)
            
            pk_columns = conn.execute(pk_query, {"schema": schema, "table_name": table_name})
            pk_cols = [col[0] for col in pk_columns]
            if pk_cols:
                print(f"  PRIMARY KEY: {', '.join(pk_cols)}")
                
                
def backup_and_drop_tables(engine, schema='public'):
    """
    Create backup tables (bkp_) and drop originals for all FastF1 tables
    """
    tables = [
        'FastF1_EventInfo', 'FastF1_SessionInfo', 'FastF1_Results',
        'FastF1_Laps', 'FastF1_Weather', 'FastF1_CarData', 'FastF1_PosData',
        'FastF1_RaceControlMsg', 'FastF1_CircuitInfo',
        'FastF1_TrackStatus', 'FastF1_SessionStatus'
    ]
    
    print("=== BACKING UP AND DROPPING FASTF1 TABLES ===\n")
    
    with engine.begin() as conn:
        for table_name in tables:
            backup_table = f"bkp_{table_name}"
            
            # Check if table exists
            table_exists_query = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = :schema 
                    AND table_name = :table_name
                )
            """)
            result = conn.execute(table_exists_query, {"schema": schema, "table_name": table_name})
            
            if not result.scalar():
                print(f"Table {table_name} does not exist, skipping...")
                continue
            
            try:
                print(f"Processing {table_name}...")
                
                # Drop backup table if it already exists
                conn.execute(text(f'DROP TABLE IF EXISTS "{schema}"."{backup_table}" CASCADE'))
                
                # Create backup with structure and data
                conn.execute(text(f"""
                    CREATE TABLE "{schema}"."{backup_table}" 
                    (LIKE "{schema}"."{table_name}" INCLUDING ALL)
                """))
                
                # Copy data
                conn.execute(text(f"""
                    INSERT INTO "{schema}"."{backup_table}" 
                    SELECT * FROM "{schema}"."{table_name}"
                """))
                
                # Get row count for verification
                count_result = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{backup_table}"'))
                row_count = count_result.scalar()
                
                print(f"  ✓ Created backup: {backup_table} ({row_count:,} rows)")
                
                # Drop original
                conn.execute(text(f"""
                    DROP TABLE IF EXISTS "{schema}"."{table_name}" CASCADE
                """))
                
                print(f"  ✓ Dropped original: {table_name}")
                
            except Exception as e:
                print(f"  ✗ Error processing {table_name}: {e}")
                raise
    
    print("\n✅ Backup and drop operation completed!")
    
    
def list_backup_tables(engine, schema='public'):
    """
    List all backup tables and their row counts
    """
    query = text("""
        SELECT 
            t.table_name,
            (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = :schema AND table_name = t.table_name) as row_count
        FROM information_schema.tables t
        WHERE t.table_schema = :schema 
        AND t.table_name LIKE 'bkp_FastF1_%'
        ORDER BY t.table_name
    """)
    
    with engine.connect() as conn:
        result = conn.execute(query, {"schema": schema})
        backups = result.fetchall()
        
        if backups:
            print("\nFound backup tables:")
            for table_name, _ in backups:
                # Get actual row count
                count_result = conn.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{table_name}"'))
                row_count = count_result.scalar()
                print(f"  - {table_name}: {row_count:,} rows")
        else:
            print("\nNo backup tables found")

# SQL-only version for direct execution
def get_backup_drop_sql(schema='public'):
    """
    Generate SQL commands for backup and drop operations
    """
    tables = [
        'FastF1_EventInfo', 'FastF1_SessionInfo', 'FastF1_Results',
        'FastF1_Laps', 'FastF1_Weather', 'FastF1_CarData', 'FastF1_PosData',
        'FastF1_RaceControlMsg', 'FastF1_CircuitInfo',
        'FastF1_TrackStatus', 'FastF1_SessionStatus'
    ]
    
    sql_commands = []
    
    for table in tables:
        sql_commands.append(f"""
-- Backup and drop {table}
DROP TABLE IF EXISTS "{schema}"."bkp_{table}" CASCADE;
CREATE TABLE "{schema}"."bkp_{table}" (LIKE "{schema}"."{table}" INCLUDING ALL);
INSERT INTO "{schema}"."bkp_{table}" SELECT * FROM "{schema}"."{table}";
DROP TABLE "{schema}"."{table}" CASCADE;
""")
    
    return '\n'.join(sql_commands)

                

# Usage example
if __name__ == "__main__":
    ...
    # # Create engine
    engine = create_engine("postgresql://postgres:postgres@localhost:5432/jolpica")
    

    dtype_mappings = clean_slate_recreate_tables(engine)

    # # 3. Insert new data
    # for table_name, df in prepared_dfs.items():
    #     auto_upsert_df(df, table_name, engine, on_conflict='skip')

    # If something goes wrong, restore from backup:
    # restore_tables_from_backup(engine)
    
    # Option 3: Restore from backups if needed
    # restore_tables_from_backup(engine)
    
    # Option 4: Get SQL commands to run manually
    # sql = get_backup_drop_sql()
    # print(sql)
    
    #dtype_mappings = setup_fastf1_database(engine)
    
    # Now you can use the dtype_mappings when inserting data with pandas
    # Example:
    # df.to_sql('FastF1_Results', engine, dtype=dtype_mappings['FastF1_Results'], 
    #           if_exists='append', index=False)