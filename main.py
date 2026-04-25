from config.db_config import get_connection
from services.reconciliation_service import reconcile

def run():

    conn = get_connection()
    conn.autocommit = False

    cursor = conn.cursor(dictionary=True)

    try:
        reconcile(cursor)
        conn.commit()
        print("Batch reconciliation completed")

    except Exception as e:
        conn.rollback()
        print("Error:", e)

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run()