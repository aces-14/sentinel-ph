import sqlite3
import pandas as pd

conn = sqlite3.connect("data/sentinel.db")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])

# Check date formats in each key table
for tbl in ["cases_national_weekly", "weather_daily", "trends_weekly", "news"]:
    df = pd.read_sql_query(f"SELECT * FROM {tbl} LIMIT 2", conn)
    print(f"\n{tbl}:")
    print(df.dtypes.to_string())
    print(df.head(2).to_string())

conn.close()
