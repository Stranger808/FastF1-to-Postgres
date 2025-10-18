# -*- coding: utf-8 -*-
"""
Created on Tue Aug  5 05:15:54 2025

@author: bradl
"""

from sqlalchemy.dialects import postgresql

def get_pg_dtypes():
    
    lap_df_mapping = {
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
    }
    
    ci_df_mapping = {
        "SessionId": postgresql.INTEGER(),
        "Feature": postgresql.TEXT(),
        "X": postgresql.FLOAT(),
        "Y": postgresql.FLOAT(),
        "Number": postgresql.SMALLINT(),
        "Letter": postgresql.TEXT(),
        "Angle": postgresql.FLOAT(),
        "Distance": postgresql.FLOAT(),
        "Rotation": postgresql.FLOAT()
    }
    
    res_df_mapping = {
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
    }
    
    rcm_df_mapping = {
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
    }
    
    weather_df_mapping = {
        "SessionId": postgresql.INTEGER(),
        "Time": postgresql.INTERVAL(),
        "AirTemp": postgresql.FLOAT(),
        "Humidity": postgresql.FLOAT(),
        "Pressure": postgresql.FLOAT(),
        "Rainfall": postgresql.BOOLEAN(),
        "TrackTemp": postgresql.FLOAT(),
        "WindDirection": postgresql.SMALLINT(),
        "WindSpeed": postgresql.FLOAT()
    }
    
    tr_status_df_mapping = {
        "SessionId": postgresql.INTEGER(),
        "Time": postgresql.INTERVAL(),
        "Status": postgresql.TEXT(),
        "Message": postgresql.TEXT()
    }
    
    s_status_df_mapping = {
        "SessionId": postgresql.INTEGER(),
        "Time": postgresql.INTERVAL(),
        "Status": postgresql.TEXT()
    }
    
    event_info_df_mapping = {
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
        "F1ApiSupport": postgresql.BOOLEAN()
    }
    
    for sn in range(1, 6):
        event_info_df_mapping[f"Session{sn}"] = postgresql.TEXT()
        event_info_df_mapping[f"Session{sn}Date"] = postgresql.TIMESTAMP()
        event_info_df_mapping[f"Session{sn}DateUtc"] = postgresql.TIMESTAMP()
    
    ses_info_df_mapping = {
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
        }
    
    
    car_df_mapping =  {
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
    }
    
    pos_df_mapping = {
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
    }
    
    # tel_df_mapping = {
    #     "SessionId": postgresql.INTEGER(),
    #     "DriverNumber": postgresql.TEXT(),
    #     "Date": postgresql.TIMESTAMP(),
    #     "SessionTime": postgresql.INTERVAL(),
    #     "DriverAhead": postgresql.TEXT(),
    #     "DistanceToDriverAhead": postgresql.FLOAT(),
    #     "Time": postgresql.INTERVAL(),
    #     "RPM": postgresql.FLOAT(),
    #     "Speed": postgresql.FLOAT(),
    #     "nGear": postgresql.SMALLINT(),
    #     "Throttle": postgresql.FLOAT(),
    #     "Brake": postgresql.BOOLEAN(),
    #     "DRS": postgresql.SMALLINT(),
    #     "Source": postgresql.TEXT(),
    #     "Distance": postgresql.FLOAT(),
    #     "RelativeDistance": postgresql.FLOAT(),
    #     "Status": postgresql.TEXT(),
    #     "X": postgresql.FLOAT(),
    #     "Y": postgresql.FLOAT(),
    #     "Z": postgresql.FLOAT()
    # }
    
    return (event_info_df_mapping, ses_info_df_mapping, lap_df_mapping, ci_df_mapping, 
            res_df_mapping, rcm_df_mapping, weather_df_mapping, tr_status_df_mapping, 
            s_status_df_mapping, car_df_mapping, pos_df_mapping)