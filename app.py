from io import StringIO, BytesIO
import uuid
import os
import subprocess
from datetime import datetime
from flask import Flask, request, render_template, flash, Response, jsonify
from config.db_config import get_connection 
import csv
import zipfile

app = Flask(__name__)
app.secret_key = "your_secret_key"
UPLOAD_FOLDER = "uploads"

@app.route('/')
def home():
    return render_template("index.html")


@app.route('/transaction', methods=['GET', 'POST'])
def transaction():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        sender = int(request.form['sender_acc'])
        receiver = int(request.form['receiver_acc'])
        amount = float(request.form['amount'])
        txn_type = request.form['txn_type']
        demo_status = request.form['demo_status']

        try:
            # Check sender
            cursor.execute("SELECT * FROM accounts WHERE account_id=%s", (sender,))
            sender_data = cursor.fetchone()
            if not sender_data:
                raise Exception("Sender account does not exist")

            # Check receiver
            cursor.execute("SELECT * FROM accounts WHERE account_id=%s", (receiver,))
            receiver_data = cursor.fetchone()
            if not receiver_data:
                raise Exception("Receiver account does not exist")

            if sender == receiver:
                raise Exception("Sender and receiver cannot be same")

            if sender_data['balance'] < amount:
                raise Exception("Insufficient balance")

            # Gateway
            cursor.execute("SELECT gateway_id FROM gateway WHERE type=%s LIMIT 1", (txn_type,))
            gateway = cursor.fetchone()
            if not gateway:
                raise Exception("Invalid transaction type")

            gateway_id = gateway['gateway_id']

            txn_id = f"TXN_{uuid.uuid4().hex[:10]}"
            idem_key = str(uuid.uuid4())

            # Insert txn
            cursor.execute("""
                INSERT INTO gateway_txn
                (gtw_txn_id, idempotency_key, gateway_id,
                 sender_account_id, receiver_account_id,
                 amount, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'PENDING')
            """, (txn_id, idem_key, gateway_id, sender, receiver, amount))

            # SUCCESS flow
            if demo_status == "SUCCESS":
                cursor.execute("SELECT balance FROM accounts WHERE account_id=%s FOR UPDATE", (sender,))
                cursor.fetchone()
                cursor.execute("SELECT balance FROM accounts WHERE account_id=%s FOR UPDATE", (receiver,))
                cursor.fetchone()

                cursor.execute("UPDATE accounts SET balance = balance - %s WHERE account_id=%s", (amount, sender))
                cursor.execute("UPDATE accounts SET balance = balance + %s WHERE account_id=%s", (amount, receiver))

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

                final_status = "SUCCESS"

            elif demo_status == "FAILED":
                final_status = "FAILED"

            else:
                final_status = "PENDING"

            # Update txn
            cursor.execute("""
                UPDATE gateway_txn
                SET status = %s
                WHERE gtw_txn_id = %s
            """, (final_status, txn_id))

            # Log
            cursor.execute("""
                INSERT INTO gateway_logs
                (gtw_txn_id, gateway_id, amount, status, log_timestamp, processed_flag)
                VALUES (%s, %s, %s, %s, NOW(), FALSE)
            """, (txn_id, gateway_id, amount, final_status))

            conn.commit()

            if final_status == "SUCCESS":
                flash("Transaction completed successfully", "success")
            elif final_status == "FAILED":
                flash("Transaction failed", "error")
            else:
                flash("Transaction is still pending", "warning")

        except Exception as e:
            conn.rollback()
            flash(str(e), "error")

        finally:
            cursor.close()
            conn.close()

    return render_template("transaction.html")

@app.route('/search_account')
def search_account():
    query = request.args.get('q')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT account_id, acc_no
            FROM accounts
            WHERE acc_no LIKE %s
            LIMIT 5
        """, (f"%{query}%",))

        results = cursor.fetchall()

        # add a display name (since you don’t have name column)
        for r in results:
            r['name'] = r['acc_no']

        return jsonify(results)

    finally:
        cursor.close()
        conn.close()


@app.route('/export_csv', methods=['POST'])
def export_csv():
    start = request.form['start'].replace('T', ' ') + ":00"
    end = request.form['end'].replace('T', ' ') + ":00"

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 🔹 Gateway logs
        cursor.execute("""
            SELECT gtw_txn_id, gateway_id, amount, status, log_timestamp
            FROM gateway_logs
            WHERE log_timestamp BETWEEN %s AND %s
        """, (start, end))
        gateway_rows = cursor.fetchall()

        # 🔹 Transaction logs
        cursor.execute("""
            SELECT gtw_txn_id, account_id, entry_type, amount, status, created_at
            FROM transaction_log
            WHERE created_at BETWEEN %s AND %s
        """, (start, end))
        txn_rows = cursor.fetchall()

        # 🔥 Create ZIP in memory
        zip_buffer = BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w') as zf:

            # Gateway CSV
            g_output = StringIO()
            g_writer = csv.writer(g_output)
            g_writer.writerow(["Transaction ID", "Gateway ID", "Amount", "Status", "Timestamp"])

            for r in gateway_rows:
                g_writer.writerow([
                    r["gtw_txn_id"],
                    r["gateway_id"],
                    r["amount"],
                    r["status"],
                    r["log_timestamp"]
                ])

            zf.writestr("gateway_logs.csv", g_output.getvalue())

            # Transaction CSV
            t_output = StringIO()
            t_writer = csv.writer(t_output)
            t_writer.writerow(["Transaction ID", "Account ID", "Type", "Amount", "Status", "Timestamp"])

            for r in txn_rows:
                t_writer.writerow([
                    r["gtw_txn_id"],
                    r["account_id"],
                    r["entry_type"],
                    r["amount"],
                    r["status"],
                    r["created_at"]
                ])

            zf.writestr("transaction_logs.csv", t_output.getvalue())

        zip_buffer.seek(0)

        return Response(
            zip_buffer,
            mimetype='application/zip',
            headers={"Content-Disposition": "attachment; filename=reconciliation_data.zip"}
        )

    finally:
        cursor.close()
        conn.close()


@app.route('/reconcile', methods=['GET', 'POST'])
def reconcile():

    if request.method == 'POST':
        input_type = request.form.get('input_type')

        try:
            # 🔥 Step 1: Create job
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO reconciliation_jobs (status)
                VALUES ('RUNNING')
            """)

            job_id = cursor.lastrowid

            conn.commit()
            cursor.close()
            conn.close()

            # 🔥 Step 2: DB MODE
            if input_type == "db":

                subprocess.Popen([
                    "python",
                    "-m",
                    "services.spark_reconciliation",
                    "DB",
                    "", "",   # no CSV paths
                    str(job_id)
                ])

            # 🔥 Step 3: CSV MODE
            elif input_type == "csv":

                gateway_file = request.files.get("gateway_file")
                txn_file = request.files.get("txn_file")

                if not gateway_file or not txn_file:
                    return jsonify({"error": "Upload both CSV files"}), 400

                os.makedirs(UPLOAD_FOLDER, exist_ok=True)

                gateway_path = os.path.join(UPLOAD_FOLDER, gateway_file.filename)
                txn_path = os.path.join(UPLOAD_FOLDER, txn_file.filename)

                gateway_file.save(gateway_path)
                txn_file.save(txn_path)

                subprocess.Popen([
                    "python",
                    "-m",
                    "services.spark_reconciliation",
                    "CSV",
                    gateway_path,
                    txn_path,
                    str(job_id)
                ])

                return jsonify({"job_id": job_id}), 200

            # 🔥 Step 4: RETURN JSON (IMPORTANT)
            return jsonify({"job_id": job_id})

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    return render_template("reconcile.html")


@app.route('/job_status/<int:job_id>')
def job_status(job_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM reconciliation_jobs WHERE job_id=%s", (job_id,))
    job = cursor.fetchone()

    return job


@app.route('/results')
def results():
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    filter_type = request.args.get('filter', 'all')

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # 🔥 Base query
    base_query = "SELECT * FROM reconciliation"

    # 🔥 Filter logic
    if filter_type == "recent":
        base_query += " ORDER BY created_at DESC"
    else:
        base_query += " ORDER BY recon_id DESC"

    # 🔥 Pagination
    base_query += " LIMIT %s OFFSET %s"

    cursor.execute(base_query, (per_page, offset))
    data = cursor.fetchall()

    # 🔥 Total count for pagination
    cursor.execute("SELECT COUNT(*) as count FROM reconciliation")
    total = cursor.fetchone()['count']

    cursor.close()
    conn.close()

    # 🔥 Add time_ago
    for row in data:
        diff = datetime.now() - row['created_at']
        diff_seconds = diff.total_seconds()

        if diff_seconds < 60:
            row['time_ago'] = f"{int(diff_seconds)}s ago"
        elif diff_seconds < 3600:
            row['time_ago'] = f"{int(diff_seconds//60)}m ago"
        elif diff_seconds < 86400:
            row['time_ago'] = f"{int(diff_seconds//3600)}h ago"
        else:
            row['time_ago'] = f"{diff.days}d ago"

    return render_template(
        "results.html",
        data=data,
        page=page,
        total=total,
        per_page=per_page,
        filter_type=filter_type
    )

if __name__ == "__main__":
    app.run(debug=True)