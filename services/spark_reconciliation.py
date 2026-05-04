from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum, when, current_timestamp
from config.db_config import get_connection
import sys

# 🔥 Get input from Flask
MODE = sys.argv[1] if len(sys.argv) > 1 else "DB"
CSV_GATEWAY_PATH = sys.argv[2] if len(sys.argv) > 2 else None
CSV_TXN_PATH = sys.argv[3] if len(sys.argv) > 3 else None

# 1. Start Spark
spark = SparkSession.builder \
    .appName("ReconciliationEngine") \
    .config("spark.jars", "file:///D:/mysql-connector-j-8.0.33/mysql-connector-j-8.0.33.jar") \
    .config("spark.local.dir", "D:/spark-temp") \
    .getOrCreate()

# 🔥 Load data
if MODE == "DB":

    gateway_df = spark.read.format("jdbc").options(
        url="jdbc:mysql://localhost:3306/tre",
        dbtable="gateway_logs",
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
    txn_df = spark.read.csv(CSV_TXN_PATH, header=True, inferSchema=True)

else:
    raise Exception("Invalid MODE")

# 🔥 Reconciliation logic (same)
ledger_df = txn_df.groupBy("gtw_txn_id").agg(
    sum(when(col("entry_type") == "DEBIT", col("amount")).otherwise(0)).alias("debit"),
    sum(when(col("entry_type") == "CREDIT", col("amount")).otherwise(0)).alias("credit")
)

recon_df = gateway_df.join(ledger_df, on="gtw_txn_id", how="left")

recon_df = recon_df.withColumn(
    "internal_status",
    when(col("debit").isNull(), "MISSING")
    .when(col("debit") != col("credit"), "PARTIAL")
    .when((col("debit") == col("amount")) & (col("credit") == col("amount")), "MATCH")
    .otherwise("AMOUNT_MISMATCH")
)

recon_df = recon_df.withColumn("processed_at", current_timestamp())

# 🔥 Insert into DB
rows = recon_df.collect()

conn = get_connection()
cursor = conn.cursor()

for row in rows:
    cursor.execute("""
        INSERT INTO reconciliation
        (gtw_txn_id, gateway_status, internal_status, mismatch_flag, remarks)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        row['gtw_txn_id'],
        row['status'],
        row['internal_status'],
        row['internal_status'] != "MATCH",
        row['internal_status']
    ))

conn.commit()
cursor.close()
conn.close()