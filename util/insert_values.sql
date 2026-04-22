INSERT INTO Users VALUES 
('U1', 'Rahul', '2000-01-01'),
('U2', 'Prajwal', '2001-02-02');

INSERT INTO Accounts VALUES 
('A1', 'U1', 'SBI', 'SBIN0001', 99000),
('A2', 'U2', 'ICICI', 'ICIC0002', 21000);

INSERT INTO UPI_Handles VALUES 
('rahul@sbi', 'A1'),
('prajwal@icici', 'A2');

INSERT INTO Transactions (from_account, to_account, amount, status, reference_id)
VALUES
('A1', 'A2', 1000, 'SUCCESS', 'abc1001'),
('A1', 'A2', 10000, 'FAILED', 'abc1002');

INSERT INTO Transaction_Log (txn_id, event_type, payer_balance_after, payee_balance_after)
VALUES
(1, 'DEBITED', 99000, NULL),
(1, 'CREDITED', 99000, 21000),
(2, 'DEBITED', 89000, NULL),
(2, 'ROLLBACK', 99000, 21000);

INSERT INTO GatewayTransactions VALUES
('G1', 'abc1001', 1000, 'SUCCESS', NOW()),
('G2', 'abc1002', 10000, 'SUCCESS', NOW());

INSERT INTO Reconciliation (reference_id, status, reason)
VALUES
('abc1001', 'MATCHED', 'exact match'),
('abc1002', 'MISMATCH', 'failed in bank');