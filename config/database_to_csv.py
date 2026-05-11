import mysql.connector
import pandas as pd
import os

# -----------------------------------
# MYSQL CONNECTION
# -----------------------------------

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="password",
    database="tre"
)

# -----------------------------------
# OUTPUT FOLDER
# -----------------------------------

OUTPUT_DIR = "exports"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------------
# FETCH ALL TABLES
# -----------------------------------

cursor = conn.cursor()

cursor.execute("SHOW TABLES")

tables = [table[0] for table in cursor.fetchall()]

print(f"Found {len(tables)} tables")

# -----------------------------------
# EXPORT EACH TABLE TO CSV
# -----------------------------------

for table in tables:

    print(f"Exporting {table}...")

    query = f"SELECT * FROM {table}"

    df = pd.read_sql(query, conn)

    csv_path = os.path.join(
        OUTPUT_DIR,
        f"{table}.csv"
    )

    df.to_csv(csv_path, index=False)

    print(f"Saved -> {csv_path}")

# -----------------------------------
# CLOSE CONNECTION
# -----------------------------------

cursor.close()
conn.close()

print("All tables exported successfully.")