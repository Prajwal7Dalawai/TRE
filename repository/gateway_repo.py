def fetch_unprocessed_logs(cursor):
    cursor.execute("""
        SELECT * FROM gateway_logs 
        WHERE processed_flag = FALSE
    """)
    return cursor.fetchall()

