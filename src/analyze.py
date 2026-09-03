# This file is used for finding finding the max temperatures
# for each day in the forcast table from the weather.db database in the /output/ directory. 
# The main function get_max() connects to the SQLite database, runs a SQL query to find 
# the maximum high temperatures for each day in the forecast table, and returns the result as a pandas DataFrame.
# The one thing about this script is that it does not have any retry logic 
# in case the database query fails or the conection to the database is lost.

import sqlite3
from pathlib import Path

import pandas as pd
DB_PATH = Path("output") / "weather.db"
def get_max():
    conn = sqlite3.connect(DB_PATH)
    hottest = pd.read_sql_query(
            "SELECT day, max(high) FROM forecast ", conn
        )
    conn.close()
    return hottest
if __name__=="__main__":
    print(get_max())