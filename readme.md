# Transaction Reconciliation Engine (TRE)

## Project Overview

Transaction Reconciliation Engine (TRE) is a banking transaction monitoring and reconciliation system developed using Flask, MySQL, and Apache Spark.

The system simulates real-world fintech reconciliation workflows by comparing external gateway logs with internal transaction logs and identifying inconsistencies such as:

* Missing transactions
* Amount mismatches
* Duplicate gateway events
* Out-of-order transaction records
* Failed or partially processed transactions
* Rollback scenarios

The project also supports CSV-based reconciliation and database-driven reconciliation using Apache Spark for scalable processing.

---

# Features

## Transaction Processing

* Create transactions using:

  * UPI
  * Net Banking
  * Bank Transfer
* Balance validation
* Sender/receiver validation
* Idempotency handling
* Transaction status tracking

## Logging System

* Gateway transaction logging
* Internal transaction logging
* Audit trail generation
* Rollback tracking

## Reconciliation Engine

* Apache Spark based reconciliation
* Database reconciliation
* CSV reconciliation
* Duplicate transaction detection
* Out-of-order transaction handling
* Amount mismatch detection
* Missing transaction detection

## Dashboard & UI

* Reconciliation result dashboard
* Pagination support
* Filters for recent records
* Status-based color coding
* Job status tracking
* CSV/ZIP export support

## Analytics (Future Scope)

* Suspicious transaction detection
* Large transaction monitoring
* Power BI dashboards
* Trend analysis and KPI reporting

---

# Tech Stack

| Technology             | Purpose                            |
| ---------------------- | ---------------------------------- |
| Flask                  | Backend web framework              |
| MySQL                  | Database                           |
| Apache Spark (PySpark) | Reconciliation processing          |
| HTML/CSS/JavaScript    | Frontend                           |
| Pandas                 | CSV handling                       |
| Power BI               | Analytics dashboard (future scope) |

---

# Project Structure

```plaintext
TRE/
│
├── app.py
├── requirements.txt
│
├── config/
│   └── db_config.py
│
├── services/
│   └── spark_reconciliation.py
│
├── templates/
│   ├── index.html
│   ├── transaction.html
│   ├── reconcile.html
│   └── results.html
│
├── uploads/
├── exports/
└── .venv/
```

---

# Database Setup

## Step 1: Create Database

Open MySQL and run:

```sql
CREATE DATABASE tre;
USE tre;
```

## Step 2: Run Schema

Execute the SQL schema file containing:

* bank
* branch
* accounts
* gateway
* gateway_txn
* transaction_log
* gateway_logs
* reconciliation
* reconciliation_jobs

---

# Virtual Environment Setup

## Step 1: Create Virtual Environment

Open terminal inside project folder:

```powershell
python -m venv .venv
```

---

## Step 2: Activate Virtual Environment

### PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
```

If execution policy error occurs:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate again:

```powershell
.\.venv\Scripts\Activate.ps1
```

Successful activation:

```plaintext
(.venv) PS D:\Projects\TRE>
```

---

# Install Dependencies

Run:

```powershell
pip install -r requirements.txt
```

---

# Requirements.txt

```txt
Flask==3.0.3
mysql-connector-python==9.2.0
pandas==2.2.3
pyspark==3.5.1
```

---

# Java Setup for Spark

Apache Spark works best with Java 17.

## Verify Java Version

```powershell
java -version
```

Recommended:

```plaintext
Java 17
```

---

# MySQL Connector JAR Setup

Download MySQL Connector/J:

* mysql-connector-j-8.0.xx.jar

Update path inside:

```python
services/spark_reconciliation.py
```

Example:

```python
.config(
    "spark.jars",
    "file:///D:/mysql-connector-j-8.0.33/mysql-connector-j-8.0.33.jar"
)
```

---

# Running the Project

## Step 1: Activate Virtual Environment

```powershell
.\.venv\Scripts\Activate.ps1
```

---

## Step 2: Start Flask Application

```powershell
python app.py
```

---

## Step 3: Open Browser

```plaintext
http://127.0.0.1:5000
```

---

# Running Reconciliation

## Database Mode

1. Open Reconciliation page
2. Select:

```plaintext
Use Database Logs
```

3. Run reconciliation

Spark will:

* Read gateway logs
* Read transaction logs
* Compare records
* Detect mismatches
* Store reconciliation results

---

## CSV Mode

1. Export logs as ZIP
2. Upload:

* gateway_logs.csv
* transaction_log.csv

3. Run reconciliation

---

# Exporting CSV Files

The application supports:

* Gateway log export
* Transaction log export
* ZIP download containing both CSV files

---

# Out-of-Order Transaction Handling

The system detects out-of-order transaction events using:

* Window functions
* Timestamp comparison
* Arrival sequence validation

This simulates:

* Delayed gateway callbacks
* Duplicate webhook events
* Async settlement delays

---

# Sample Reconciliation Results

The reconciliation engine classifies transactions as:

| Status           | Meaning                         |
| ---------------- | ------------------------------- |
| MATCH            | Gateway and internal logs match |
| MISMATCH         | Logs do not match               |
| MISSING_INTERNAL | Internal transaction missing    |
| AMOUNT_MISMATCH  | Amount mismatch detected        |

---

# Future Enhancements

* Large transaction detection
* Fraud/risk scoring
* Power BI integration
* Advanced analytics dashboards
* Real-time reconciliation
* Kafka event streaming

---

# Contributors

Developed as part of internship project implementation.

Team Size: 5 Members

---

