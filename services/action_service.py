def rollback_transaction(cursor, txn_id):
    cursor.execute("""
        SELECT account_id, entry_type, amount 
        FROM transaction_log 
        WHERE gtw_txn_id = %s
    """, (txn_id,))
    
    entries = cursor.fetchall()

    for e in entries:
        if e["entry_type"] == "DEBIT":
            cursor.execute("""
                UPDATE accounts 
                SET balance = balance + %s 
                WHERE account_id = %s
            """, (e["amount"], e["account_id"]))
        else:
            cursor.execute("""
                UPDATE accounts 
                SET balance = balance - %s 
                WHERE account_id = %s
            """, (e["amount"], e["account_id"]))