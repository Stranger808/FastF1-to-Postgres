# -*- coding: utf-8 -*-

import fastf1_download as f1_dl
import fastf1_upsert as f1_up
import fastf1_index as f1_idx
import fastf1_create_tables as f1_ct
import fastf1_check_nulls as f1_cn
import fastf1
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql
import os
import io

# from dotenv import load_dotenv
import itertools
import warnings
import logging
import time



# Set up the root logger first
logging.basicConfig(level=logging.INFO)

# Get the Fast-F1 logger specifically
ff1_logger = logging.getLogger("fastf1")
ff1_logger.setLevel(logging.DEBUG)
ff1_logger.propagate = False  # This prevents propagation to root logger

# Create formatter
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# # Console handler
# console_handler = logging.StreamHandler()
# console_handler.setLevel(logging.DEBUG)
# console_handler.setFormatter(formatter)

# File handler
file_handler = logging.FileHandler("fastf1_debug.log")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# Add handlers to the Fast-F1 logger
ff1_logger.addHandler(file_handler)
# ff1_logger.addHandler(console_handler)

# Enable Fast-F1's cache
cache_loc = r"C:\Users\bradl\OneDrive\Documents\F1 Data\fastf1_cache"
fastf1.Cache.enable_cache(cache_loc)

# Suppress FutureWarning messages
warnings.simplefilter(action="ignore", category=FutureWarning)


# %%

DATABASE_URL = r"postgresql://postgres:postgres@localhost:5432/jolpica"
engine = create_engine(DATABASE_URL)

year_range = (2019, 2019)
round_range = (3,) # () for none 
ses_list = [5,]

(
    event_info_df,
    session_info_df,
    results_df,
    lap_df,
    weather_df,
    car_data_df,
    pos_data_df,
    rcm_df,
    ci_df,
    tr_status_df,
    s_status_df,
    upsert_results
) = f1_dl.download_data(year_range, round_range=round_range, ses_list=ses_list, engine=engine, 
                        return_data=True)

#%%

# # 2. Analyze the data for nulls BEFORE creating tables
# print("Analyzing data for null values...")
# null_report, constraint_issues = f1_cn.analyze_fastf1_nulls(
#     event_info_df,
#     session_info_df,
#     results_df,
#     lap_df,
#     weather_df,
#     car_data_df,
#     pos_data_df,
#     rcm_df,
#     ci_df,
#     tr_status_df,
#     s_status_df
# )

# # 3. Review the constraint issues
# if constraint_issues:
#     print("\n⚠️ Found constraint issues that need handling:")
#     for table, issues in constraint_issues.items():
#         print(f"\n{table}:")
#         for issue in issues:
#             print(f"  - {issue['column']}: {issue['null_count']} nulls ({issue['null_percentage']:.2f}%)")

# # 4. Prepare the dataframes to handle nulls
# dataframes = {
#     'FastF1_EventInfo': event_info_df,
#     'FastF1_SessionInfo': session_info_df,
#     'FastF1_Results': results_df,
#     'FastF1_Laps': lap_df,
#     'FastF1_Weather': weather_df,
#     'FastF1_CarData': car_data_df,
#     'FastF1_PosData': pos_data_df,
#     'FastF1_RaceControlMsg': rcm_df,
#     'FastF1_CircuitInfo': ci_df,
#     'FastF1_TrackStatus': tr_status_df,
#     'FastF1_SessionStatus': s_status_df
# }

# # Handle nulls based on the analysis
# prepared_dfs = f1_up.prepare_fastf1_data_for_db(dataframes)

# # 5. Create the database connection
# # DATABASE_URL = r"postgresql://postgres:postgres@localhost:5432/jolpica"
# # engine = create_engine(DATABASE_URL)

# # 6. Create the database schema
# print("\nCreating database schema...")
# dtype_mappings = f1_ct.f1_clean_and_recreate_tables(engine)

# # 7. Insert the prepared data
# print("\nInserting data into database...")
# for table_name, df in prepared_dfs.items():
#     print(f"\nInserting {len(df)} rows into {table_name}...")
#     try:
#         # Use the auto_upsert function with the prepared data
#         result = f1_up.auto_upsert_df(
#             df, 
#             table_name, 
#             engine, 
#             on_conflict='skip',  # or 'update' if you want to update existing records
#             chunksize=10000
#         )
#         print(f"  Result: {result}")
#     except Exception as e:
#         print(f"  Error inserting into {table_name}: {e}")

# # 8. Verify the data was inserted correctly
# print("\nVerifying database structure...")
# f1_ct.verify_table_structure(engine)




