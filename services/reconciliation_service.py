from repository.gateway_repo import fetch_unprocessed_logs
from repository.txn_repo import get_internal_summary
from repository.recon_repo import insert_reconciliation
from services.action_service import rollback_transaction

def classify(gateway, internal):

    if not internal:
        return "MISSING_INTERNAL", "REFUND"

    if abs(internal["net_amount"]) != gateway["amount"]:
        return "AMOUNT_MISMATCH", "FLAG"

    if gateway["status"] != internal["status"]:
        return "MISMATCH", "ROLLBACK"

    if internal["entry_count"] != 2:
        return "MISMATCH", "INVESTIGATE"

    return "MATCH", "NONE"


def reconcile(cursor):

    logs = fetch_unprocessed_logs(cursor)

    for log in logs:
        txn_id = log["gtw_txn_id"]

        internal = get_internal_summary(cursor, txn_id)

        result, action = classify(log, internal)

        insert_reconciliation(cursor, (
            txn_id,
            log["status"],
            internal["status"] if internal else None,
            log["amount"],
            abs(internal["net_amount"]) if internal else None,
            result,
            action
        ))

        # 🔥 controlled actions
        if action == "ROLLBACK":
            rollback_transaction(cursor, txn_id)

        # mark processed
        cursor.execute("""
            UPDATE gateway_logs 
            SET processed_flag = TRUE 
            WHERE gtw_txn_id = %s
        """, (txn_id,))