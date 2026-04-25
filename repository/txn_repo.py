def get_internal_summary(cursor, txn_id):
    cursor.execute("""
        SELECT 
            gtw_txn_id,
            SUM(CASE 
                WHEN entry_type='CREDIT' THEN amount 
                ELSE -amount 
            END) AS net_amount,
            COUNT(*) AS entry_count,
            MIN(status) AS status
        FROM transaction_log
        WHERE gtw_txn_id = %s
        GROUP BY gtw_txn_id
    """, (txn_id,))
    
    return cursor.fetchone()