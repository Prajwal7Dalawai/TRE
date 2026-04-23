import mysql.connector
import uuid

try:
    conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="password",
    database="tre"
    )
    cursor = conn.cursor()
    if cursor:
        print("Connected succesfully to the database")
except Exception as e:
    print(e)

# def start_transaction():
#     txn_id = str(uuid.uuid4())
#     cursor.execute()