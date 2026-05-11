import mysql.connector
import random
from datetime import timedelta

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="password",
    database="tre"
)

cursor = conn.cursor(dictionary=True)

# -----------------------------------
# FETCH SUCCESS LOGS
# -----------------------------------

cursor.execute("""
SELECT *
FROM gateway_logs
WHERE status='SUCCESS'
LIMIT 5
""")

logs = cursor.fetchall()

print(f"Fetched {len(logs)} logs")

# -----------------------------------
# CREATE OUT-OF-ORDER EVENTS
# -----------------------------------

for log in logs:

    # Delayed timestamp
    delayed_time = log['log_timestamp'] + timedelta(
        minutes=random.randint(5, 60)
    )

    # Insert delayed duplicate log
    cursor.execute("""
        INSERT INTO gateway_logs
        (
            gtw_txn_id,
            gateway_id,
            amount,
            status,
            log_timestamp,
            processed_flag
        )
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (
        log['gtw_txn_id'],
        log['gateway_id'],
        log['amount'],
        log['status'],
        delayed_time,
        False
    ))

conn.commit()

cursor.close()
conn.close()

print("Out-of-order dataset generated.")