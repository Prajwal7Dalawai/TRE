from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum, when, current_timestamp
from config.db_config import get_connection
import sys

# 🔥 Args from Flask
MODE = sys.argv[1] if len(sys.argv) > 1 else "DB"
CSV_GATEWAY_PATH = sys.argv[2] if len(sys.argv) > 2 else None
CSV_TXN_PATH = sys.argv[3] if len(sys.argv) > 3 else None
JOB_ID = int(sys.argv[4]) if len(sys.argv) > 4 else None

try:
    # 🔥 Start Spark
    spark = SparkSession.builder \
        .appName("ReconciliationEngine") \
        .config("spark.jars", "file:///D:/mysql-connector-j-8.0.33/mysql-connector-j-8.0.33.jar") \
        .config("spark.local.dir", "D:/spark-temp") \
        .getOrCreate()

    # 🔥 Load Data
    if MODE == "DB":

        gateway_df = spark.read.format("jdbc").options(
            url="jdbc:mysql://localhost:3306/tre",
            dbtable="(SELECT * FROM gateway_logs WHERE processed_flag = FALSE) as t",
            user="root",
            password="password",
            driver="com.mysql.cj.jdbc.Driver"
        ).load()

        txn_df = spark.read.format("jdbc").options(
            url="jdbc:mysql://localhost:3306/tre",
            dbtable="transaction_log",
            user="root",
            password="password",
            driver="com.mysql.cj.jdbc.Driver"
        ).load()

    elif MODE == "CSV":

        if not CSV_GATEWAY_PATH or not CSV_TXN_PATH:
            raise Exception("CSV paths not provided")

        gateway_df = spark.read.csv(CSV_GATEWAY_PATH, header=True, inferSchema=True)
        gateway_df = gateway_df.selectExpr(
            "`Transaction ID` as gtw_txn_id",
            "`Gateway ID` as gateway_id",
            "`Amount` as amount",
            "`Status` as status",
            "`Timestamp` as log_timestamp"
        )
        txn_df = spark.read.csv(CSV_TXN_PATH, header=True, inferSchema=True)
        txn_df = txn_df.selectExpr(
            "`Transaction ID` as gtw_txn_id",
            "`Account ID` as account_id",
            "`Type` as entry_type",
            "`Amount` as amount",
            "`Status` as status",
            "`Timestamp` as created_at"
        )

    else:
        raise Exception("Invalid MODE")

    # 🔥 Aggregate ledger
    ledger_df = txn_df.groupBy("gtw_txn_id").agg(
        sum(when(col("entry_type") == "DEBIT", col("amount")).otherwise(0)).alias("debit"),
        sum(when(col("entry_type") == "CREDIT", col("amount")).otherwise(0)).alias("credit")
    )

    # 🔥 Join
    recon_df = gateway_df.join(ledger_df, on="gtw_txn_id", how="left")

    # 🔥 Internal amount = credit (or debit — consistent)
    recon_df = recon_df.withColumn(
        "internal_amount",
        when(col("credit").isNull(), 0).otherwise(col("credit"))
    )

    # 🔥 Classification
    recon_df = recon_df.withColumn(
        "result",
        when(col("debit").isNull(), "MISSING_INTERNAL")
        .when((col("debit") == col("amount")) & (col("credit") == col("amount")), "MATCH")
        .when(col("debit") != col("credit"), "MISMATCH")
        .otherwise("AMOUNT_MISMATCH")
    )

    recon_df = recon_df.withColumn("processed_at", current_timestamp())

    # 🔥 Collect
    rows = recon_df.collect()

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    for row in rows:

        action = "NONE"

        # 🔥 Handle rollback
        if row['result'] != "MATCH":
            action = "ROLLBACK"

            cursor.execute("""
                SELECT account_id, entry_type, amount
                FROM transaction_log
                WHERE gtw_txn_id = %s
            """, (row['gtw_txn_id'],))

            entries = cursor.fetchall()

            for entry in entries:
                if entry['entry_type'] == "DEBIT":
                    cursor.execute("""
                        UPDATE accounts
                        SET balance = balance + %s
                        WHERE account_id = %s
                    """, (entry['amount'], entry['account_id']))

                elif entry['entry_type'] == "CREDIT":
                    cursor.execute("""
                        UPDATE accounts
                        SET balance = balance - %s
                        WHERE account_id = %s
                    """, (entry['amount'], entry['account_id']))

            cursor.execute("""
                UPDATE gateway_txn
                SET status = 'ROLLEDBACK'
                WHERE gtw_txn_id = %s
            """, (row['gtw_txn_id'],))

        # 🔥 Insert reconciliation (FIXED)
        cursor.execute("""
            INSERT INTO reconciliation
            (gtw_txn_id, gateway_status, internal_status,
             gateway_amount, internal_amount, result, action_taken)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            row['gtw_txn_id'],
            row['status'],
            row['result'],
            row['amount'],
            row['internal_amount'],
            row['result'],
            action
        ))

        # 🔥 Mark processed (only DB mode)
        if MODE == "DB":
            cursor.execute("""
                UPDATE gateway_logs
                SET processed_flag = TRUE
                WHERE log_id = %s
            """, (row['log_id'],))

    conn.commit()

    # 🔥 Update job status SUCCESS
    if JOB_ID:
        cursor.execute("""
            UPDATE reconciliation_jobs
            SET status='SUCCESS', completed_at=NOW()
            WHERE job_id=%s
        """, (JOB_ID,))
        conn.commit()

    cursor.close()
    conn.close()

    spark.stop()

except Exception as e:

    conn = get_connection()
    cursor = conn.cursor()

    if JOB_ID:
        cursor.execute("""
            UPDATE reconciliation_jobs
            SET status='FAILED', message=%s, completed_at=NOW()
            WHERE job_id=%s
        """, (str(e), JOB_ID))
        conn.commit()

    cursor.close()
    conn.close()

    raise