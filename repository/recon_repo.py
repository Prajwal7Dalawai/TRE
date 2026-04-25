def insert_reconciliation(cursor, data):
    cursor.execute("""
        INSERT INTO reconciliation
        (gtw_txn_id, gateway_status, internal_status,
         gateway_amount, internal_amount, result, action_taken)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, data)