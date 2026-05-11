import mysql.connector
import random
import uuid
from datetime import datetime, timedelta


# MYSQL CONNECTION
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="password",
    database="tre"
)

cursor = conn.cursor()

# FETCH ACCOUNTS
cursor.execute("SELECT account_id FROM accounts")
accounts = [row[0] for row in cursor.fetchall()]

print(f"Fetched {len(accounts)} accounts")

# CONFIG
NUM_TRANSACTIONS = 5000

statuses = ['SUCCESS', 'FAILED', 'PENDING']

start_time = datetime(2026, 4, 1, 10, 0, 0)

gateway_txn_data = []
gateway_logs_data = []
transaction_logs_data = []

# GENERATE DATA
for i in range(NUM_TRANSACTIONS):

    sender = random.choice(accounts)
    receiver = random.choice(accounts)

    while receiver == sender:
        receiver = random.choice(accounts)

    txn_id = f"TXN_{10000 + i}"

    idempotency_key = str(uuid.uuid4())

    gateway_id = 1

    amount = round(random.uniform(100, 50000), 2)

    status = random.choices(
        statuses,
        weights=[85, 10, 5],
        k=1
    )[0]

    txn_time = start_time + timedelta(
        seconds=random.randint(1, 200000)
    )

    # gateway_txn
    gateway_txn_data.append(
        (
            txn_id,
            idempotency_key,
            gateway_id,
            sender,
            receiver,
            amount,
            status,
            txn_time,
            txn_time
        )
    )

    # gateway_logs
    gateway_logs_data.append(
        (
            txn_id,
            gateway_id,
            amount,
            status,
            txn_time,
            False
        )
    )

    # transaction_log
    # ONLY SUCCESS

    if status == "SUCCESS":

        # DEBIT
        transaction_logs_data.append(
            (
                txn_id,
                sender,
                'DEBIT',
                amount,
                'SUCCESS',
                txn_time
            )
        )

        # CREDIT
        transaction_logs_data.append(
            (
                txn_id,
                receiver,
                'CREDIT',
                amount,
                'SUCCESS',
                txn_time
            )
        )


# INSERT gateway_txn

cursor.executemany("""
INSERT INTO gateway_txn
(
    gtw_txn_id,
    idempotency_key,
    gateway_id,
    sender_account_id,
    receiver_account_id,
    amount,
    status,
    created_at,
    updated_at
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
""", gateway_txn_data)

# INSERT gateway_logs

cursor.executemany("""
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
""", gateway_logs_data)

# INSERT transaction_log

cursor.executemany("""
INSERT INTO transaction_log
(
    gtw_txn_id,
    account_id,
    entry_type,
    amount,
    status,
    created_at
)
VALUES (%s,%s,%s,%s,%s,%s)
""", transaction_logs_data)

conn.commit()

print(f"Inserted {NUM_TRANSACTIONS} gateway transactions")
print(f"Inserted {len(gateway_logs_data)} gateway logs")
print(f"Inserted {len(transaction_logs_data)} transaction logs")


# CLOSE

cursor.close()
conn.close()

print("Dataset generation completed.")