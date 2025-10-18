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
import itertools
import warnings
import logging
import time

import fastf1_utils as f1_utils

# Set up the root logger first
logging.basicConfig(level=logging.INFO)
logging.captureWarnings(True)

# Set up FastF1 logger with file output
ff1_logger = f1_utils.setup_logger_with_file(
    "fastf1", 
    "fastf1_debug.log", 
    logging.DEBUG
)

# Set up warnings logger
warnings_logger = logging.getLogger('py.warnings')
file_handler = logging.FileHandler("fastf1_debug.log")
file_handler.setLevel(logging.WARNING)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
warnings_logger.addHandler(file_handler)

# Define critical messages that should raise exceptions
critical_messages = [
    "Car position data is unavailable!",
    # Add more critical messages here as needed
    # "Another critical message",
]

# Set up critical handlers
ff1_critical_handler = f1_utils.setup_critical_warning_handler(
    "fastf1", 
    critical_messages, 
    RuntimeError
)

f1_utils.setup_critical_warnings_handler(
    critical_messages, 
    RuntimeError
)

# Enable Fast-F1's cache
cache_loc = r"C:\Users\bradl\OneDrive\Documents\F1 Data\fastf1_cache"
fastf1.Cache.enable_cache(cache_loc)
#%%
# Your main code
try:
    warnings.simplefilter(action="ignore", category=FutureWarning)
    
    DATABASE_URL = r"postgresql://postgres:postgres@localhost:5432/jolpica"
    engine = create_engine(DATABASE_URL)
    
    year_range = (2018, 2018)
    round_range = (1,1)
    ses_list = None
    
    # (
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
    #     s_status_df,
    #     upsert_results
    # ) = f1_dl.download_data(year_range, round_range=round_range, ses_list=ses_list, engine=engine, 
    #                         return_data=True)

except RuntimeError as e:
    if any(msg in str(e) for msg in critical_messages):
        print(f"Script stopped due to critical warning: {e}")
        # Handle as needed - exit, skip, etc.
    else:
        raise  # Re-raise if it's a different RuntimeError
