# -*- coding: utf-8 -*-
"""
Created on Sat Aug  2 11:24:40 2025

@author: bradl
"""

import pandas as pd
from sqlalchemy import create_engine, text

def create_optimized_fastf1_schema(engine, schema='public'):
    """
    Create optimal indexes, keys, and constraints for FastF1 tables
    """
    
    # Define table structures with optimal configurations
    table_configs = {
        'FastF1_EventInfo': {
            'primary_key': ['Year', 'RoundNumber', 'TestNumber'],
            'indexes': [
                ('idx_schedule_year', ['Year']),
                ('idx_schedule_eventformat', ['EventFormat']),
                ('idx_schedule_location', ['Location', 'Country']),
            ],
            'unique_constraints': [
                ('unique_schedule', ['Year', 'RoundNumber', 'TestNumber'])
            ]
        },
        
        'FastF1_SessionInfo': {
            'primary_key': ['SessionID'],
            'indexes': [
                ('idx_sessioninfo_event', ['EventID']),
                ('idx_sessioninfo_type', ['SessionType']),
                ('idx_sessioninfo_dates', ['StartDate', 'EndDate']),
                ('idx_sessioninfo_composite', ['EventID', 'SessionType']),
            ],
            'unique_constraints': [
                ('unique_sessioninfo', ['SessionID'])
            ]
        },
        
        'FastF1_Results': {
            'primary_key': ['SessionID', 'DriverNumber'],
            'indexes': [
                ('idx_results_driver', ['DriverNumber']),
                ('idx_results_team', ['TeamId']),
                ('idx_results_position', ['Position']),
                ('idx_results_points', ['Points']),
                ('idx_results_status', ['Status']),
                # Covering index for qualifying analysis
                ('idx_results_quali_covering', ['SessionID', 'DriverNumber'], 
                 ['Q1', 'Q2', 'Q3', 'Position', 'GridPosition']),
            ],
            'unique_constraints': [
                ('unique_results', ['SessionID', 'DriverNumber'])
            ]
        },
        
        'FastF1_Laps': {
            'surrogate_key': True,
            'indexes': [
                ('idx_laps_session_driver', ['SessionID', 'DriverNumber']),
                ('idx_laps_session_lap', ['SessionID', 'LapNumber']),
                ('idx_laps_driver_lap', ['DriverNumber', 'LapNumber']),
                ('idx_laps_compound', ['Compound']),
                ('idx_laps_deleted', ['Deleted']),
                ('idx_laps_pb', ['IsPersonalBest']),
                # Covering index for lap time analysis
                ('idx_laps_analysis_covering', 
                 ['SessionID', 'DriverNumber', 'LapNumber'], 
                 ['LapTime', 'Sector1Time', 'Sector2Time', 'Sector3Time', 'Compound', 'TyreLife']),
                # Index for stint analysis
                ('idx_laps_stint', ['SessionID', 'DriverNumber', 'Stint']),
                # Time-based queries
                ('idx_laps_time', ['SessionID', 'Time']),
            ],
            'unique_constraints': [
                ('unique_laps', ['SessionID', 'Session', 'Time', 'DriverNumber'])
            ]
        },
        
        'FastF1_Weather': {
            'primary_key': ['SessionID', 'Time'],
            'indexes': [
                ('idx_weather_session', ['SessionID']),
                # Covering index for weather conditions lookup
                ('idx_weather_covering', ['SessionID', 'Time'], 
                 ['AirTemp', 'TrackTemp', 'WindSpeed', 'WindDirection', 'Rainfall']),
            ],
            'unique_constraints': [
                ('unique_weather', ['SessionID', 'Time'])
            ]
        },
        
        'FastF1_Telemetry': {
            'surrogate_key': True,
            'indexes': [
                ('idx_telemetry_session_driver', ['SessionID', 'DriverNumber']),
                ('idx_telemetry_time', ['SessionID', 'DriverNumber', 'Time']),
                ('idx_telemetry_distance', ['SessionID', 'DriverNumber', 'Distance']),
                ('idx_telemetry_source', ['Source']),
                # Covering index for telemetry analysis
                ('idx_telemetry_covering', 
                 ['SessionID', 'DriverNumber', 'Time'], 
                 ['Speed', 'RPM', 'nGear', 'Throttle', 'Brake', 'DRS']),
                # Spatial index for track position
                ('idx_telemetry_position', ['SessionID', 'X', 'Y']),
            ],
            'unique_constraints': [
                ('unique_telemetry', ['SessionID', 'DriverNumber', 'Time', 'Source'])
            ]
        },
        
        'FastF1_RaceControlMsg': {
            'primary_key': ['SessionID', 'Time', 'Category', 'Status', 'RacingNumber', 'Sector'],
            'indexes': [
                ('idx_rcm_session', ['SessionID']),
                ('idx_rcm_category', ['Category']),
                ('idx_rcm_flag', ['Flag']),
                ('idx_rcm_driver', ['RacingNumber']),
                ('idx_rcm_time', ['SessionID', 'Time']),
            ],
            'unique_constraints': [
                ('unique_rcm', ['SessionID', 'Time', 'Category', 'Status', 'RacingNumber', 'Sector'])
            ]
        },
        
        'FastF1_CircuitInfo': {
            'primary_key': ['SessionID', 'Feature', 'Number', 'Letter'],
            'indexes': [
                ('idx_ci_session', ['SessionID']),
                ('idx_ci_feature', ['Feature']),
                # Spatial index for circuit features
                ('idx_ci_spatial', ['X', 'Y']),
            ],
            'unique_constraints': [
                ('unique_ci', ['SessionID', 'Feature', 'Number', 'Letter'])
            ]
        },
        
        'FastF1_TrackStatus': {
            'primary_key': ['SessionID', 'Time'],
            'indexes': [
                ('idx_ts_session', ['SessionID']),
                ('idx_ts_status', ['Status']),
                ('idx_ts_time', ['SessionID', 'Time']),
            ],
            'unique_constraints': [
                ('unique_ts', ['SessionID', 'Time'])
            ]
        },
        
        'FastF1_SessionStatus': {
            'primary_key': ['SessionID', 'Time', 'Status'],
            'indexes': [
                ('idx_ss_session', ['SessionID']),
                ('idx_ss_status', ['Status']),
                ('idx_ss_time', ['SessionID', 'Time']),
            ],
            'unique_constraints': [
                ('unique_ss', ['SessionID', 'Time', 'Status'])
            ]
        }
    }
    
    with engine.begin() as conn:
        # Create each table's indexes and constraints
        for table_name, config in table_configs.items():
            print(f"\nConfiguring {table_name}...")
            
            # Add surrogate key if needed
            if config.get('surrogate_key', False):
                try:
                    conn.execute(text(f"""
                        ALTER TABLE "{schema}"."{table_name}" 
                        ADD COLUMN IF NOT EXISTS id BIGSERIAL PRIMARY KEY
                    """))
                    print("  ✓ Added surrogate primary key")
                except Exception as e:
                    print(f"  - Surrogate key error: {e}")
            
            # Create primary key if specified
            elif 'primary_key' in config:
                pk_cols = ', '.join([f'"{col}"' for col in config['primary_key']])
                try:
                    # Check if primary key exists
                    check_pk = text("""
                        SELECT 1 FROM information_schema.table_constraints 
                        WHERE table_schema = :schema 
                        AND table_name = :table_name 
                        AND constraint_type = 'PRIMARY KEY'
                    """)
                    result = conn.execute(check_pk, {"schema": schema, "table_name": table_name})
                    
                    if not result.fetchone():
                        conn.execute(text(f"""
                            ALTER TABLE "{schema}"."{table_name}" 
                            ADD PRIMARY KEY ({pk_cols})
                        """))
                        print(f"  ✓ Added primary key: {config['primary_key']}")
                except Exception as e:
                    print(f"  - Primary key error: {e}")
            
            # Create indexes
            for idx_name, idx_cols, *include_cols in config.get('indexes', []):
                try:
                    idx_cols_str = ', '.join([f'"{col}"' for col in idx_cols])
                    
                    if include_cols:  # Covering index
                        include_str = ', '.join([f'"{col}"' for col in include_cols[0]])
                        conn.execute(text(f"""
                            CREATE INDEX IF NOT EXISTS {idx_name}
                            ON "{schema}"."{table_name}" ({idx_cols_str})
                            INCLUDE ({include_str})
                        """))
                        print(f"  ✓ Created covering index: {idx_name}")
                    else:  # Regular index
                        conn.execute(text(f"""
                            CREATE INDEX IF NOT EXISTS {idx_name}
                            ON "{schema}"."{table_name}" ({idx_cols_str})
                        """))
                        print(f"  ✓ Created index: {idx_name}")
                except Exception as e:
                    print(f"  - Index error {idx_name}: {e}")
            
            # Create unique constraints
            for constraint_name, constraint_cols in config.get('unique_constraints', []):
                try:
                    cols_str = ', '.join([f'"{col}"' for col in constraint_cols])
                    conn.execute(text(f"""
                        ALTER TABLE "{schema}"."{table_name}"
                        ADD CONSTRAINT IF NOT EXISTS {constraint_name}
                        UNIQUE ({cols_str})
                    """))
                    print(f"  ✓ Created unique constraint: {constraint_name}")
                except Exception as e:
                    print(f"  - Constraint error {constraint_name}: {e}")

def create_foreign_keys(engine, schema='public'):
    """
    Create foreign key relationships between tables
    """
    foreign_keys = [
        # SessionInfo references
        ('FastF1_Results', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
        ('FastF1_Laps', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
        ('FastF1_Weather', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
        ('FastF1_Telemetry', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
        ('FastF1_RaceControlMsg', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
        ('FastF1_CircuitInfo', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
        ('FastF1_TrackStatus', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
        ('FastF1_SessionStatus', 'FastF1_SessionInfo', 'SessionID', 'SessionID'),
    ]
    
    with engine.begin() as conn:
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

def create_performance_indexes(engine, schema='public'):
    """
    Create additional performance indexes for common query patterns
    """
    performance_indexes = [
        # Driver performance across sessions
        """CREATE INDEX IF NOT EXISTS idx_driver_performance
           ON "FastF1_Results" ("DriverNumber", "SessionID")
           INCLUDE ("Position", "Points", "Q1", "Q2", "Q3")""",
        
        # Team performance
        """CREATE INDEX IF NOT EXISTS idx_team_performance
           ON "FastF1_Results" ("TeamId", "SessionID")
           INCLUDE ("Position", "Points")""",
        
        # Lap time progression
        """CREATE INDEX IF NOT EXISTS idx_lap_progression
           ON "FastF1_Laps" ("SessionID", "DriverNumber", "LapNumber")
           WHERE "Deleted" = false AND "LapTime" IS NOT NULL""",
        
        # Tire strategy analysis
        """CREATE INDEX IF NOT EXISTS idx_tire_strategy
           ON "FastF1_Laps" ("SessionID", "DriverNumber", "Stint", "Compound")
           INCLUDE ("TyreLife", "LapTime")""",
        
        # Weather impact analysis
        """CREATE INDEX IF NOT EXISTS idx_weather_impact
           ON "FastF1_Weather" ("SessionID", "Time")
           WHERE "Rainfall" > 0""",
        
        # DRS usage
        """CREATE INDEX IF NOT EXISTS idx_drs_usage
           ON "FastF1_Telemetry" ("SessionID", "DriverNumber")
           WHERE "DRS" > 0""",
        
        # Safety car periods
        """CREATE INDEX IF NOT EXISTS idx_safety_car
           ON "FastF1_TrackStatus" ("SessionID", "Time")
           WHERE "Status" IN ('4', '5', '6')""",  # VSC, SC statuses
    ]
    
    with engine.begin() as conn:
        for idx_sql in performance_indexes:
            try:
                conn.execute(text(idx_sql))
                print("✓ Created performance index")
            except Exception as e:
                print(f"✗ Performance index error: {e}")

def analyze_and_vacuum(engine, schema='public'):
    """
    Analyze and vacuum tables for optimal performance
    """
    tables = [
        'FastF1_EventInfo', 'FastF1_SessionInfo', 'FastF1_Results',
        'FastF1_Laps', 'FastF1_Weather', 'FastF1_Telemetry',
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

# Usage
if __name__ == "__main__":
    engine = create_engine("postgresql://postgres:postgres@localhost:5432/jolpica")
    
    # Create all optimizations
    create_optimized_fastf1_schema(engine)
    create_foreign_keys(engine)
    create_performance_indexes(engine)
    analyze_and_vacuum(engine)