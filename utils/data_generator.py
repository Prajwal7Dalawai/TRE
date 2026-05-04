import random
import uuid
from faker import Faker
from config.db_config import get_connection

fake = Faker()


# 🔥 RESET TABLES (important to avoid FK + duplicate issues)
def reset_tables(cursor):
    print("Resetting tables...")

    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

    tables = [
        "reconciliation",
        "transaction_log",
        "gateway_logs",
        "gateway_txn",
        "accounts",
        "branch",
        "bank",
        "gateway"
    ]

    for table in tables:
        cursor.execute(f"TRUNCATE TABLE {table}")

    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")


# 🔹 SEED BASE DATA
def seed_base_data(cursor):
    print("Seeding base data...")

    # BANKS
    cursor.execute(
        "INSERT INTO bank (bank_code, bank_name) VALUES ('HDFC','HDFC Bank')"
    )
    hdfc_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO bank (bank_code, bank_name) VALUES ('SBI','State Bank of India')"
    )
    sbi_id = cursor.lastrowid

    # BRANCHES
    cursor.execute(
        "INSERT INTO branch (bank_id, ifsc, address) VALUES (%s,'HDFC0001','Bangalore')",
        (hdfc_id,)
    )
    branch1_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO branch (bank_id, ifsc, address) VALUES (%s,'SBI0001','Mysore')",
        (sbi_id,)
    )
    branch2_id = cursor.lastrowid

    branches = [
        (branch1_id, hdfc_id),
        (branch2_id, sbi_id)
    ]

    # ACCOUNTS
    print("Creating accounts...")
    for i in range(20):
        branch_id, bank_id = random.choice(branches)

        cursor.execute("""
            INSERT INTO accounts
            (cust_id, bank_id, branch_id, acc_no, balance, account_type, dob)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            100 + i,
            bank_id,
            branch_id,
            f"ACC{1000+i}",
            random.randint(5000, 20000),
            random.choice(['SAVINGS', 'CURRENT']),
            fake.date_of_birth(minimum_age=18, maximum_age=50)
        ))

    # GATEWAY
    cursor.execute("""
        INSERT INTO gateway (name, type)
        VALUES ('PhonePe', 'UPI')
    """)

    gateway_id = cursor.lastrowid

    return gateway_id


# 🔹 GENERATE TRANSACTIONS
def generate_transactions(cursor, gateway_id, n=1000):
    print(f"Generating {n} transactions...")

    # fetch accounts
    cursor.execute("SELECT account_id FROM accounts")
    accounts = [row[0] for row in cursor.fetchall()]

    for _ in range(n):

        txn_id = f"TXN_{uuid.uuid4().hex[:10]}"
        idem_key = str(uuid.uuid4())

        sender = random.choice(accounts)
        receiver = random.choice(accounts)

        while receiver == sender:
            receiver = random.choice(accounts)

        amount = random.randint(50, 500)

        scenario = random.choices(
            ["MATCH", "MISSING_INTERNAL", "STATUS_MISMATCH", "AMOUNT_MISMATCH"],
            weights=[70, 10, 10, 10]
        )[0]

        # 🔹 gateway txn
        txn_status = "SUCCESS" if scenario != "STATUS_MISMATCH" else "FAILED"

        cursor.execute("""
            INSERT INTO gateway_txn
            (gtw_txn_id, idempotency_key, gateway_id,
             sender_account_id, receiver_account_id,
             amount, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            txn_id, idem_key, gateway_id,
            sender, receiver, amount, txn_status
        ))

        # 🔹 gateway logs (external)
        log_amount = amount
        log_status = "SUCCESS"

        if scenario == "AMOUNT_MISMATCH":
            log_amount += random.randint(10, 50)

        cursor.execute("""
            INSERT INTO gateway_logs
            (gtw_txn_id, gateway_id, amount, status, log_timestamp, processed_flag)
            VALUES (%s, %s, %s, %s, NOW(), FALSE)
        """, (
            txn_id, gateway_id, log_amount, log_status
        ))

        # 🔥 INTERNAL LEDGER
        if scenario != "MISSING_INTERNAL":

            cursor.execute("""
                INSERT INTO transaction_log
                (gtw_txn_id, account_id, entry_type, amount, status)
                VALUES (%s, %s, 'DEBIT', %s, 'SUCCESS')
            """, (txn_id, sender, amount))

            cursor.execute("""
                INSERT INTO transaction_log
                (gtw_txn_id, account_id, entry_type, amount, status)
                VALUES (%s, %s, 'CREDIT', %s, 'SUCCESS')
            """, (txn_id, receiver, amount))


# 🔥 MAIN
def main():
    conn = get_connection()
    cursor = conn.cursor()

    try:
        reset_tables(cursor)

        gateway_id = seed_base_data(cursor)

        generate_transactions(cursor, gateway_id, 1000)

        conn.commit()
        print("✅ Full data setup completed successfully")

    except Exception as e:
        conn.rollback()
        print("❌ Error:", e)

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()