import csv
from io import StringIO
import uuid
import os
import subprocess

from flask import Flask, request, redirect, render_template, flash, Response, jsonify
from config.db_config import get_connection

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

@app.route('/export_csv', methods=['GET', 'POST'])
def export_csv():
    start = request.form['start'].replace('T', ' ') + ":00"
    end = request.form['end'].replace('T', ' ') + ":00"

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT gtw_txn_id, gateway_id, amount, status, log_timestamp
            FROM gateway_logs
            WHERE log_timestamp BETWEEN %s AND %s
            ORDER BY log_timestamp
        """, (start, end))

        rows = cursor.fetchall()

        output = StringIO()
        writer = csv.writer(output)

        writer.writerow(["Transaction ID", "Gateway ID", "Amount", "Status", "Timestamp"])

        for row in rows:
            writer.writerow([
                row["gtw_txn_id"],
                row["gateway_id"],
                row["amount"],
                row["status"],
                row["log_timestamp"]
            ])

        output.seek(0)

        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=gateway_logs.csv"}
        )

    finally:
        cursor.close()
        conn.close()


@app.route('/reconcile', methods=['GET', 'POST'])
def reconcile():

    if request.method == 'POST':
        input_type = request.form.get('input_type')

        try:
            # 🔥 DB MODE
            if input_type == "db":

                subprocess.Popen([
                    "python",
                    "-m",
                    "services.spark_reconciliation",
                    "DB"
                ])

                flash("Reconciliation started using DATABASE", "success")

            # 🔥 CSV MODE
            elif input_type == "csv":

                gateway_file = request.files.get("gateway_file")
                txn_file = request.files.get("txn_file")

                if not gateway_file or not txn_file:
                    flash("Upload both CSV files", "error")
                    return redirect('/reconcile')

                gateway_path = os.path.join(UPLOAD_FOLDER, gateway_file.filename)
                txn_path = os.path.join(UPLOAD_FOLDER, txn_file.filename)

                gateway_file.save(gateway_path)
                txn_file.save(txn_path)

                subprocess.Popen([
                    "python",
                    "services/spark_reconciliation.py",
                    "CSV",
                    gateway_path,
                    txn_path
                ])

                flash("Reconciliation started using CSV", "success")

            else:
                flash("Invalid input type", "error")

        except Exception as e:
            flash(str(e), "error")

        return redirect('/reconcile')

    return render_template("reconcile.html")

@app.route('/results')
def results():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 🔥 Get latest reconciliation records
        cursor.execute("""
            SELECT *
            FROM reconciliation
            ORDER BY recon_id DESC
            LIMIT 100
        """)
        data = cursor.fetchall()

        return render_template("results.html", data=data)

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    app.run(debug=True)