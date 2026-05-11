from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    sum,
    when,
    current_timestamp,
    row_number
)
from pyspark.sql.window import Window
from config.db_config import get_connection
import sys
# ARGS FROM FLASK
MODE = sys.argv[1] if len(sys.argv) > 1 else "DB"
CSV_GATEWAY_PATH = sys.argv[2] if len(sys.argv) > 2 else None
CSV_TXN_PATH = sys.argv[3] if len(sys.argv) > 3 else None
JOB_ID = int(sys.argv[4]) if len(sys.argv) > 4 else None

try:

    # START SPARK
    spark = SparkSession.builder \
        .appName("ReconciliationEngine") \
        .config(
            "spark.jars",
            "file:///D:/mysql-connector-j-8.0.33/mysql-connector-j-8.0.33.jar"
        ) \
        .config("spark.local.dir", "D:/spark-temp") \
        .getOrCreate()

    # LOAD DATA
    if MODE == "DB":

        gateway_df = spark.read.format("jdbc").options(
        url="jdbc:mysql://localhost:3306/tre",
        dbtable="""
        (
            SELECT
                gl.log_id,
                gl.gtw_txn_id,
                gl.gateway_id,
                gl.amount,
                gl.status,
                gl.log_timestamp,
                gl.processed_flag,
                gt.created_at,
                gt.sender_account_id,
                acc.balance AS sender_balance
            FROM gateway_logs gl
            JOIN gateway_txn gt
                ON gl.gtw_txn_id = gt.gtw_txn_id
            JOIN accounts acc
                ON gt.sender_account_id = acc.account_id
            WHERE gl.processed_flag = FALSE
        ) as t
        """,
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

        gateway_df = spark.read.csv(
            CSV_GATEWAY_PATH,
            header=True,
            inferSchema=True
        )

        gateway_df = gateway_df.selectExpr(
            "`Transaction ID` as gtw_txn_id",
            "`Gateway ID` as gateway_id",
            "`Amount` as amount",
            "`Status` as status",
            "`Timestamp` as log_timestamp"
        )

        txn_df = spark.read.csv(
            CSV_TXN_PATH,
            header=True,
            inferSchema=True
        )

        txn_df = txn_df.selectExpr(
            "`Transaction ID` as gtw_txn_id",
            "`Account ID` as account_id",
            "`Type` as entry_type",
            "`Amount` as amount",
            "`Status` as status",
            "`Timestamp` as created_at"
        )

        # For CSV mode
        gateway_df = gateway_df.withColumn(
            "created_at",
            col("log_timestamp")
        )

    else:
        raise Exception("Invalid MODE")

    # OUT OF ORDER DETECTION
    expected_window = Window.orderBy("created_at")

    gateway_df = gateway_df.withColumn(
        "expected_seq",
        row_number().over(expected_window)
    )

    actual_window = Window.orderBy("log_timestamp")

    gateway_df = gateway_df.withColumn(
        "actual_seq",
        row_number().over(actual_window)
    )

    gateway_df = gateway_df.withColumn(
        "out_of_order_flag",
        when(
            col("expected_seq") != col("actual_seq"),
            True
        ).otherwise(False)
    )

    # LARGE TXN DETECTION
    LARGE_TXN_THRESHOLD = 20000
    gateway_df = gateway_df.withColumn(
        "large_txn_flag",

        when(
            (col("amount") >= LARGE_TXN_THRESHOLD) &
            (col("amount") >= (col("sender_balance") * 0.8)),
            True
        ).otherwise(False)
    )


    # AGGREGATE LEDGER
    ledger_df = txn_df.groupBy("gtw_txn_id").agg(
        sum(
            when(
                col("entry_type") == "DEBIT",
                col("amount")
            ).otherwise(0)
        ).alias("debit"),

        sum(
            when(
                col("entry_type") == "CREDIT",
                col("amount")
            ).otherwise(0)
        ).alias("credit")
    )

    # JOIN
    recon_df = gateway_df.join(
        ledger_df,
        on="gtw_txn_id",
        how="left"
    )

    # INTERNAL AMOUNT
    recon_df = recon_df.withColumn(
        "internal_amount",
        when(
            col("credit").isNull(),
            0
        ).otherwise(col("credit"))
    )

    # CLASSIFICATION
    recon_df = recon_df.withColumn(
        "result",

        when(
            col("out_of_order_flag") == True,
            "OUT_OF_ORDER"
        )

        .when(
            col("large_txn_flag") == True,
            "LARGE_TRANSACTION"
        )

        .when(
            col("debit").isNull(),
            "MISSING_INTERNAL"
        )

        .when(
            (col("debit") == col("amount")) &
            (col("credit") == col("amount")),
            "MATCH"
        )

        .when(
            col("debit") != col("credit"),
            "MISMATCH"
        )

        .otherwise("AMOUNT_MISMATCH")
    )

    recon_df = recon_df.withColumn(
        "processed_at",
        current_timestamp()
    )

    # COLLECT
    rows = recon_df.collect()

    conn = get_connection()

    cursor = conn.cursor(dictionary=True, buffered=True)

    for row in rows:


        cursor.execute("""
            SELECT recon_id
            FROM reconciliation
            WHERE gtw_txn_id = %s
        """, (row['gtw_txn_id'],))

        existing = cursor.fetchone()

        if existing:
            continue

        action = "NONE"
        if row['debit'] is None:
            internal_status = "MISSING"

        elif row['debit'] == row['credit']:
            internal_status = "SUCCESS"

        else:
            internal_status = "FAILED"

        if row['result'] == "LARGE_TRANSACTION":

            cursor.execute("""
                INSERT INTO large_transaction_audit
                (gtw_txn_id, amount, threshold_limit, remark)
                VALUES (%s, %s, %s, %s)
            """, (
                row['gtw_txn_id'],
                row['amount'],
                25000,
                'High value transaction flagged'
            ))


        if row['result'] in (
            "MISMATCH",
            "AMOUNT_MISMATCH",
            "MISSING_INTERNAL"
        ):

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
                    """, (
                        entry['amount'],
                        entry['account_id']
                    ))

                elif entry['entry_type'] == "CREDIT":

                    cursor.execute("""
                        UPDATE accounts
                        SET balance = balance - %s
                        WHERE account_id = %s
                    """, (
                        entry['amount'],
                        entry['account_id']
                    ))

            cursor.execute("""
                UPDATE gateway_txn
                SET status = 'ROLLEDBACK'
                WHERE gtw_txn_id = %s
            """, (row['gtw_txn_id'],))

        cursor.execute("""
            INSERT INTO reconciliation
            (
                gtw_txn_id,
                gateway_status,
                internal_status,
                gateway_amount,
                internal_amount,
                result,
                action_taken
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            row['gtw_txn_id'],
            row['status'],
            internal_status,
            row['amount'],
            row['internal_amount'],
            row['result'],
            action
        ))


        if MODE == "DB":

            cursor.execute("""
                UPDATE gateway_logs
                SET processed_flag = TRUE
                WHERE log_id = %s
            """, (row['log_id'],))

    conn.commit()


    if JOB_ID:

        cursor.execute("""
            UPDATE reconciliation_jobs
            SET
                status='SUCCESS',
                completed_at=NOW()
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
            SET
                status='FAILED',
                message=%s,
                completed_at=NOW()
            WHERE job_id=%s
        """, (str(e), JOB_ID))

        conn.commit()

    cursor.close()
    conn.close()

    raise