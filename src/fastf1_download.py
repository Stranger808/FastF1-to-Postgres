import fastf1
from fastf1.core import DataNotLoadedError
import fastf1_upsert as f1_up
import pandas as pd
import numpy as np
import itertools
import logging
import fastf1_utils as f1_utils

# Set up critical handling for any logger
logger = logging.getLogger("f1_dl")

# Define what messages should be critical for this module
critical_messages = [
    "Car position data is unavailable!",
    # Add more critical messages here as needed
    # "Another critical message",
]

# Set up the critical handler
critical_handler = f1_utils.setup_critical_warning_handler(
    "f1_dl",
    critical_messages,
    ValueError  # Can use different exception types
)

def get_event_cols():
    
    common_cols = ['SessionID',]
    
    ses_info_df_cols = ['SessionID',
     'EventID',
     'SessionName',
     'SessionType',
     'StartDate',
     'EndDate',
     'GmtOffset',
     'Time0',
     'StartTime',
     'ScheduledLaps']
    
    event_info_df_cols = ['EventID',
     'CountryID',
     'CircuitID',
     'Year',
     'RoundNumber',
     'TestNumber',
     'Country',
     'CountryCode',
     'Location',
     'Circuit',
     'OfficialEventName',
     'EventDate',
     'EventName',
     'EventFormat',
     'Session1',
     'Session1Date',
     'Session1DateUtc',
     'Session2',
     'Session2Date',
     'Session2DateUtc',
     'Session3',
     'Session3Date',
     'Session3DateUtc',
     'Session4',
     'Session4Date',
     'Session4DateUtc',
     'Session5',
     'Session5Date',
     'Session5DateUtc',
     'F1ApiSupport']
    
    results_df_cols = common_cols + ['DriverNumber',
     'BroadcastName',
     'Abbreviation',
     'DriverId',
     'TeamName',
     'TeamColor',
     'TeamId',
     'FirstName',
     'LastName',
     'FullName',
     'HeadshotUrl',
     'CountryCode',
     'Position',
     'ClassifiedPosition',
     'GridPosition',
     'Q1',
     'Q2',
     'Q3',
     'Time',
     'Status',
     'Points',
     'Laps']

    lap_df_cols = common_cols + ['Session',
     'Time',
     'Driver',
     'DriverNumber',
     'LapTime',
     'LapNumber',
     'Stint',
     'PitOutTime',
     'PitInTime',
     'Sector1Time',
     'Sector2Time',
     'Sector3Time',
     'Sector1SessionTime',
     'Sector2SessionTime',
     'Sector3SessionTime',
     'SpeedI1',
     'SpeedI2',
     'SpeedFL',
     'SpeedST',
     'IsPersonalBest',
     'Compound',
     'TyreLife',
     'FreshTyre',
     'Team',
     'LapStartTime',
     'LapStartDate',
     'TrackStatus',
     'Position',
     'Deleted',
     'DeletedReason',
     'FastF1Generated',
     'IsAccurate']

    weather_df_cols = common_cols + ['Time',
     'AirTemp',
     'Humidity',
     'Pressure',
     'Rainfall',
     'TrackTemp',
     'WindDirection',
     'WindSpeed']

    # tel_df_cols = common_cols + ["DriverNumber",] + ['Date',
    #  'SessionTime',
    #  'DriverAhead',
    #  'DistanceToDriverAhead',
    #  'Time',
    #  'RPM',
    #  'Speed',
    #  'nGear',
    #  'Throttle',
    #  'Brake',
    #  'DRS',
    #  'Source',
    #  'Distance',
    #  'RelativeDistance',
    #  'Status',
    #  'X',
    #  'Y',
    #  'Z']
    
    tel_common_cols = ['Date',
     'SessionTime',
     'Time',
     'Source',]
    
    car_df_cols = common_cols + ["DriverNumber",] + tel_common_cols + ['RPM',
         'Speed',
         'nGear',
         'Throttle',
         'Brake',
         'DRS',
         'DriverAhead',
         'DistanceToDriverAhead',
         'Distance',
         'RelativeDistance',]
    
    pos_df_cols = common_cols + ["DriverNumber",] + tel_common_cols + ['Status',
    'X',
    'Y',
    'Z']

    rcm_df_cols = common_cols + ['Time',
     'Category',
     'Message',
     'Status',
     'Flag',
     'Scope',
     'Sector',
     'RacingNumber',
     'Lap']

    ci_df_cols = common_cols + ['Feature',] + ['X', 'Y', 'Number', 'Letter', 
                                               'Angle', 'Distance'] + ['Rotation',]

    tr_status_df_cols = common_cols + ['Time', 'Status', 'Message']

    s_status_df_cols = common_cols + ['Time', 'Status']
    
    return (ses_info_df_cols, event_info_df_cols, results_df_cols, lap_df_cols, 
            weather_df_cols, car_df_cols, pos_df_cols, 
            rcm_df_cols, ci_df_cols, tr_status_df_cols, s_status_df_cols)

def pg_insert(dataframes: dict, engine, already_prepared=False):
    """
    Insert FastF1 dataframes into PostgreSQL using the fixed auto_upsert function
    
    Parameters:
    -----------
    dataframes : dict
        Dictionary of {table_name: DataFrame} to insert
    engine : sqlalchemy.Engine
        Database connection engine
    already_prepared : bool
        If True, skip the prepare_dataframes_for_insert step
        
    Returns:
    --------
    dict : Results for each table insertion
    """
    upsert_results = dict()
    
    # 1. Fix column names (SessionId -> SessionID, etc.)
    fixed_dataframes = f1_up.fix_dataframe_column_names(dataframes)
    
    # 2. Prepare data (fix data types, handle nulls) - ONLY if not already prepared
    if already_prepared:
        prepared_dfs = fixed_dataframes
    else:
        prepared_dfs = f1_up.prepare_dataframes_for_insert(fixed_dataframes)
    
    # 3. Insert data using the fixed auto_upsert function
    for table_name, df in prepared_dfs.items():
        print(f"\nInserting {len(df)} rows into {table_name}...")
        
        # Add explicit Position column check for FastF1_Laps
        if table_name == 'FastF1_Laps' and 'Position' in df.columns:
            # Ensure Position is integer type
            df['Position'] = df['Position'].apply(
                lambda x: int(x) if pd.notna(x) else None
            )
        
        try:
            # Use the new fixed version that handles column ordering internally
            result = f1_up.auto_upsert_df(
                df, 
                table_name, 
                engine, 
                on_conflict='skip',
                chunksize=10000
            )
            print(f"  Result: {result}")
            
            upsert_results[table_name] = result
            
        except Exception as e:
            print(f"  Error: {e}")
            print(f"  DataFrame columns: {list(df.columns)}")
            if len(df) > 0:
                print(f"  First row data types: {df.iloc[0].apply(type).to_dict()}")
                print(f"  First row values: {df.iloc[0].to_dict()}")
            
            # Store error in results
            upsert_results[table_name] = {
                'error': str(e),
                'rows_affected': 0,
                'total_input_rows': len(df)
            }

    # 4. Summary
    print("\n=== INSERTION SUMMARY ===")
    total_inserted = 0
    total_attempted = 0
    
    for table_name, result in upsert_results.items():
        if 'error' in result:
            print(f"{table_name}: ❌ ERROR - {result['error']}")
        else:
            rows_affected = result.get('rows_affected', 0)
            total_rows = result.get('total_input_rows', 0)
            total_inserted += rows_affected
            total_attempted += total_rows
            
            if rows_affected == total_rows:
                print(f"{table_name}: ✅ {rows_affected}/{total_rows} rows inserted")
            elif rows_affected == 0:
                print(f"{table_name}: ⏭️  {rows_affected}/{total_rows} rows (all skipped - already exist)")
            else:
                print(f"{table_name}: ⚠️  {rows_affected}/{total_rows} rows inserted (some skipped)")
    
    print(f"\nTotal: {total_inserted}/{total_attempted} rows inserted across all tables")
    
    return upsert_results


def fmt_session_data(data, cols):
    df = pd.DataFrame(columns=cols)
    data_cols = list(data.columns)
    df[data_cols] = data[data_cols]
    return df

def get_session_data(row, ses_num, engine=None, max_sessions=5, return_data=False):
    
    
    #global ts
    
    (session_info_df_cols, event_info_df_cols, results_df_cols, lap_df_cols, weather_df_cols, 
     car_df_cols, pos_df_cols, rcm_df_cols, 
     ci_df_cols, tr_status_df_cols, s_status_df_cols) = get_event_cols()
    
    year = row["Year"]
    
    event_format = row["EventFormat"]
    if event_format == 'testing':
        test_num = row["TestNumber"]
        ts = fastf1.get_testing_session(year, test_num, ses_num)
    else:
        test_num = np.nan
        ts = fastf1.get_session(year, row["RoundNumber"], ses_num)
        
    ts.load()
    
    # Session Info
    si = ts.session_info
    
    si["Time0"] = pd.NaT
    try:
        si["Time0"] = ts.t0_date
    except DataNotLoadedError as e:
        print(e)
        
    si["StartTime"] = ts.session_start_time
    si["ScheduledLaps"] = ts.total_laps
    
    ses_info_dict = {'SessionID': si['Key'],
                     'EventID': si['Meeting']['Key'],
                     'SessionName': si['Name'],
                     'SessionType': si['Type'],
                     'StartDate': si['StartDate'],
                     'EndDate': si['EndDate'],
                     'GmtOffset': si['GmtOffset'], 
                     'Time0': si["Time0"],
                     'StartTime': si["StartTime"],
                     'ScheduledLaps': si["ScheduledLaps"]
                     }
    
    session_info_df = pd.DataFrame([ses_info_dict])
    
    ses_info_dict['Circuit'] = si['Meeting']['Circuit']['ShortName']
    ses_info_dict['CircuitID'] = si['Meeting']['Circuit']['Key']
    ses_info_dict['CountryCode'] = si['Meeting']['Country']['Code']
    ses_info_dict['CountryID'] = si['Meeting']['Country']['Key']
    
    # Session results
    session_res_df = fmt_session_data(ts.results, results_df_cols)
    
    # Lap data
    session_lap_df = pd.DataFrame(columns=lap_df_cols)
    session_laps = ts.laps
    if "Qualifying" in row[f"Session{ses_num}"]:
        q1, q2, q3 = session_laps.split_qualifying_sessions()
        q1, q2, q3 = q1.copy(), q2.copy(), q3.copy()
        q1["Session"] = row[f"Session{ses_num}"] + " 1"
        q2["Session"] = row[f"Session{ses_num}"] + " 2"
        q3["Session"] = row[f"Session{ses_num}"] + " 3"
        session_laps_ud = pd.concat([q1, q2, q3], ignore_index=True)
    else:
        session_laps_ud = session_laps.copy()
        session_laps_ud["Session"] = row[f"Session{ses_num}"]   
    lap_cols = list(session_laps_ud.columns)
    session_lap_df[lap_cols] = session_laps_ud[lap_cols]

    # # Telemetry
    # driver_nums = ts.drivers
    # session_tel_df = pd.DataFrame(columns=tel_df_cols)
    # for driver in driver_nums:
    #     print(f"Loading telemetry data for driver {driver}...")
    #     driver_laps = session_laps.loc[session_laps["DriverNumber"] == str(driver)]
    #     if len(driver_laps):
    #         driver_tel_df = pd.DataFrame(columns=tel_df_cols)
    #         driver_tel = driver_laps.telemetry
    #         tel_cols = list(driver_tel.columns)
    #         driver_tel_df[tel_cols] = driver_tel[tel_cols]
    #         driver_tel_df["DriverNumber"] = driver
    #         session_tel_df = pd.concat([session_tel_df, driver_tel_df], ignore_index=True)
        
    # Split Telemetry
    driver_nums = ts.drivers

    session_car_data = pd.DataFrame(columns=car_df_cols)
    session_pos_data = pd.DataFrame(columns=pos_df_cols)
    
    for driver in driver_nums:
        print(f"Loading telemetry data for driver {driver}...")
        driver_laps = session_laps.loc[session_laps["DriverNumber"].astype(str) == str(driver)]
        
        if len(driver_laps):
            
            driver_car_data = pd.DataFrame(columns=car_df_cols)
            driver_pos_data = pd.DataFrame(columns=pos_df_cols)
            
            try:
                pos_data = driver_laps.get_pos_data(pad=1, pad_side='both')
                car_data = driver_laps.get_car_data(pad=1, pad_side='both')
                
                drv_ahead = car_data.iloc[1:-1] \
                    .add_driver_ahead() \
                    .loc[:, ('DriverAhead', 'DistanceToDriverAhead',
                             'Date', 'Time', 'SessionTime')]

                car_data = car_data.add_distance().add_relative_distance()
                car_data = car_data.merge_channels(drv_ahead) #, frequency=frequency)           
                    
                car_cols = list(car_data.columns)
                driver_car_data[car_cols] = car_data[car_cols]
                driver_car_data["DriverNumber"] = driver
                session_car_data = pd.concat([session_car_data, driver_car_data], ignore_index=True) 
                    
                pos_cols = list(pos_data.columns)
                driver_pos_data[pos_cols] = pos_data[pos_cols]
                driver_pos_data["DriverNumber"] = driver
                session_pos_data = pd.concat([session_pos_data, driver_pos_data], ignore_index=True) 
                
            except ValueError as e:
                if any(msg in str(e) for msg in critical_messages):
                    print(f"Critical error in module: {e}")
                    # Handle appropriately
                else:
                    raise
            
            except DataNotLoadedError as e:
                print(e)
            
       
    
    # Weather data
    session_weather_df = fmt_session_data(ts.weather_data, weather_df_cols)
    
    
    # Race Control messages
    session_rcm_df = fmt_session_data(ts.race_control_messages, rcm_df_cols)
    

    # Extra circuit info
    session_ci = ts.get_circuit_info()
    corners = session_ci.corners
    corners["Feature"] = "Corners"
    marshal_lights = session_ci.marshal_lights
    marshal_lights["Feature"] = "Marshal Light"
    marshal_sectors = session_ci.marshal_sectors
    marshal_sectors["Feature"] = "Marshal Sectors"
    temp_ci_df = pd.DataFrame()
    for feature_df in (corners, marshal_lights, marshal_sectors):
        temp_ci_df = pd.concat([temp_ci_df, feature_df], ignore_index=True)
    rotation = session_ci.rotation    
    temp_ci_df["Rotation"] = rotation 
    session_ci_df = fmt_session_data(temp_ci_df, ci_df_cols)
    
    
    # Track status
    session_tr_status_df = fmt_session_data(ts.track_status, tr_status_df_cols)
    
    # Session status
    session_s_status_df = fmt_session_data(ts.session_status, s_status_df_cols)
                
    for df in (session_res_df, session_lap_df, session_weather_df, session_car_data, session_pos_data, 
               session_rcm_df, session_ci_df, session_tr_status_df, session_s_status_df):    
        df["SessionID"] = si["Key"]
    
    upsert_results = dict()
    
    table_dict = {
        "FastF1_SessionInfo": session_info_df,
        "FastF1_Results": session_res_df,
        "FastF1_Laps": session_lap_df,
        "FastF1_Weather": session_weather_df,
        "FastF1_CarData": session_car_data,
        "FastF1_PosData": session_pos_data,
        "FastF1_RaceControlMsg": session_rcm_df,
        "FastF1_CircuitInfo": session_ci_df,
        "FastF1_TrackStatus": session_tr_status_df,
        "FastF1_SessionStatus": session_s_status_df
    }
    #global formatted_tables
    formatted_tables = f1_up.prepare_dataframes_for_insert(table_dict)
    
    if engine:
        
        upsert_results = pg_insert(formatted_tables, engine, already_prepared=True)
        
    if return_data:
        
        return (formatted_tables["FastF1_SessionInfo"], ses_info_dict, formatted_tables["FastF1_Results"], 
                formatted_tables["FastF1_Laps"], 
                formatted_tables["FastF1_Weather"], formatted_tables["FastF1_CarData"], formatted_tables["FastF1_PosData"], 
            formatted_tables["FastF1_RaceControlMsg"], formatted_tables["FastF1_CircuitInfo"], 
            formatted_tables["FastF1_TrackStatus"], formatted_tables["FastF1_SessionStatus"],
            upsert_results)
    
    else:
        return (upsert_results,)

def get_schedule_data(year):
    
    schedule = fastf1.get_event_schedule(year)
    events = schedule.copy()

    #events.reset_index(inplace=True, drop=True)
    events.insert(0, "Year", year)

    events.insert(loc=2, column="TestNumber", value=np.nan)
    test_counter = itertools.count(start=1, step=1)
    events["TestNumber"] = events.apply(
        lambda row: (
            next(test_counter) if row["EventFormat"] == "testing" else np.nan
        ),
        axis=1,
    )
    events["TestNumber"] = events["TestNumber"].astype("Int64")
     
    return events

def get_event_data(row, ses_list=None, engine=None, max_sessions=5, return_data=False): 
    
    (ses_info_df_cols, event_info_df_cols, results_df_cols, lap_df_cols, 
     weather_df_cols, car_df_cols, pos_df_cols, rcm_df_cols, 
     ci_df_cols, tr_status_df_cols, s_status_df_cols) = get_event_cols()
    
    event_ses_info_df = pd.DataFrame(columns=ses_info_df_cols)
    event_res_df = pd.DataFrame(columns=results_df_cols)
    event_lap_df = pd.DataFrame(columns=lap_df_cols)
    event_weather_df = pd.DataFrame(columns=weather_df_cols)
    event_car_df = pd.DataFrame(columns=car_df_cols)
    event_pos_df = pd.DataFrame(columns=pos_df_cols)
    event_rcm_df = pd.DataFrame(columns=rcm_df_cols)
    event_ci_df = pd.DataFrame(columns=ci_df_cols)
    event_tr_status_df = pd.DataFrame(columns=tr_status_df_cols)
    event_s_status_df = pd.DataFrame(columns=s_status_df_cols)
    event_info_df = pd.DataFrame(columns=event_info_df_cols)
    
    row_cols = list(row.index)
    valid_sessions = [int(s[-1]) for s in row_cols if s[:-1] == "Session" and row[s] != "None"] 
    
    if ses_list:
        valid_sessions = [s for s in ses_list if s in valid_sessions]
    
    upsert_results = dict()
    
    for ses_num in valid_sessions:
        
        if return_data:
            (session_info_df, session_info_dict, session_res_df, session_lap_df, 
             session_weather_df, session_car_df, session_pos_df,
                session_rcm_df, session_ci_df, session_tr_status_df, session_s_status_df,
                session_upsert_results
                ) = get_session_data(row, ses_num, engine=engine, return_data=return_data)
            
        else:
            session_upsert_results = get_session_data(row, ses_num, engine=engine, return_data=return_data)[0]
        
        if session_upsert_results:
            upsert_results[ses_num] = session_upsert_results
            
        event_ses_info_df = pd.concat([event_ses_info_df, session_info_df], ignore_index=True)
        event_res_df = pd.concat([event_res_df, session_res_df], ignore_index=True)
        event_lap_df = pd.concat([event_lap_df, session_lap_df], ignore_index=True)
        event_weather_df = pd.concat([event_weather_df, session_weather_df], ignore_index=True)
        event_car_df = pd.concat([event_car_df, session_car_df], ignore_index=True)
        event_pos_df = pd.concat([event_pos_df, session_pos_df], ignore_index=True)
        event_rcm_df = pd.concat([event_rcm_df, session_rcm_df], ignore_index=True)
        event_ci_df = pd.concat([event_ci_df, session_ci_df], ignore_index=True)
        event_tr_status_df = pd.concat([event_tr_status_df, session_tr_status_df], ignore_index=True)
        event_s_status_df = pd.concat([event_s_status_df, session_s_status_df], ignore_index=True)
        
        
    event_info_df = pd.concat([event_info_df, pd.DataFrame([row])], ignore_index=True)
    event_info_df['EventID'] = session_info_dict['EventID']
    event_info_df['Circuit'] = session_info_dict['Circuit']
    event_info_df['CircuitID'] = session_info_dict['CircuitID']
    event_info_df['CountryCode'] = session_info_dict['CountryCode']
    event_info_df['CountryID'] = session_info_dict['CountryID']
    
    table_dict = {"FastF1_EventInfo": event_info_df}
    formatted_tables = f1_up.prepare_dataframes_for_insert(table_dict)
    
    if engine:
        
        event_upsert_results = pg_insert(formatted_tables, engine)
        upsert_results["FastF1_EventInfo"] = event_upsert_results["FastF1_EventInfo"]
            
    if return_data:
        
        return (event_ses_info_df, event_res_df, event_lap_df, event_weather_df, event_car_df, event_pos_df,
                event_rcm_df, event_ci_df, event_tr_status_df, event_s_status_df, formatted_tables["FastF1_EventInfo"],
                upsert_results)
    
    else:
        
        return (upsert_results,)

def download_data(year_range, round_range=None, ses_list=None, engine=None, return_data=False):
    
    (
        all_event_info_df,
        session_info_df,
        results_df,
        lap_df,
        weather_df,
        car_df,
        pos_df,
        rcm_df,
        ci_df,
        tr_status_df,
        s_status_df,
    ) = [pd.DataFrame()] * 11
    
    upsert_results = dict()
    
    for year in range(year_range[0], year_range[1] + 1):

        season_upsert_results = dict()        

        schedule = get_schedule_data(year)
        events = (schedule[max((round_range[0] - 1),0):round_range[-1]].copy() if round_range 
                  else schedule.copy())
        
        for _, row in events.iterrows():    
            
            if return_data:
                
                (event_ses_info_df, event_res_df, event_lap_df, event_weather_df, event_car_df, event_pos_df, 
                        event_rcm_df, event_ci_df, event_tr_status_df, event_s_status_df, 
                        event_info_df, event_upsert_results) = get_event_data(
                            row, ses_list=ses_list, engine=engine, return_data=return_data)
                
                all_event_info_df = pd.concat([all_event_info_df, event_info_df], ignore_index=True)
                session_info_df = pd.concat([session_info_df, event_ses_info_df], ignore_index=True)
                results_df = pd.concat([results_df, event_res_df], ignore_index=True)
                lap_df = pd.concat([lap_df, event_lap_df], ignore_index=True)
                weather_df = pd.concat([weather_df, event_weather_df], ignore_index=True)
                car_df = pd.concat([car_df, event_car_df], ignore_index=True)
                pos_df = pd.concat([pos_df, event_pos_df], ignore_index=True)
                rcm_df = pd.concat([rcm_df, event_rcm_df], ignore_index=True)
                ci_df = pd.concat([ci_df, event_ci_df], ignore_index=True)
                tr_status_df = pd.concat([tr_status_df, event_tr_status_df], ignore_index=True)
                s_status_df = pd.concat([s_status_df, event_s_status_df], ignore_index=True)
                
            else:
                
                event_upsert_results = get_event_data(row, ses_list=ses_list, engine=engine)[0]
            
            if event_upsert_results:
                season_upsert_results[row["RoundNumber"]] = event_upsert_results
                
        if season_upsert_results:
            upsert_results[year] = season_upsert_results
            
    if return_data:
        
            return (
                all_event_info_df,
                session_info_df,
                results_df,
                lap_df,
                weather_df,
                car_df,
                pos_df,
                rcm_df,
                ci_df,
                tr_status_df,
                s_status_df,
                upsert_results
            )
        
    else:
        return (upsert_results,)
    
#%%            
if __name__ == "__main__":
    
    year = 2018
    round_range = (1,)
    ses_list = (1,)
    engine = None
    return_data = True
    schedule = get_schedule_data(year)
    events = (schedule[max((round_range[0] - 1),0):round_range[-1]].copy() if round_range 
              else schedule.copy())
    
    for _, row in events.iterrows():    
        
        if return_data:
            
            (event_ses_info_df, event_res_df, event_lap_df, event_weather_df, event_car_df, event_pos_df, 
                    event_rcm_df, event_ci_df, event_tr_status_df, event_s_status_df, 
                    event_info_df, event_upsert_results) = get_event_data(
                        row, ses_list=ses_list, engine=engine, return_data=return_data)
            

        
        
        
        
        
        
        

    
