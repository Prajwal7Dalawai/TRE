create database if not exists tre;
use tre;

CREATE TABLE bank (
    bank_id INT PRIMARY KEY AUTO_INCREMENT,
    bank_code VARCHAR(20) UNIQUE NOT NULL,
    bank_name VARCHAR(100) NOT NULL
);

CREATE TABLE branch (
    branch_id INT PRIMARY KEY AUTO_INCREMENT,
    bank_id INT NOT NULL,
    ifsc VARCHAR(20) UNIQUE NOT NULL,
    address VARCHAR(255),

    FOREIGN KEY (bank_id) REFERENCES bank(bank_id)
);

CREATE TABLE accounts (
    account_id INT PRIMARY KEY AUTO_INCREMENT,
    cust_id INT NOT NULL,
    bank_id INT NOT NULL,
    branch_id INT NOT NULL,
    acc_no VARCHAR(30) UNIQUE NOT NULL,

    balance DECIMAL(15,2) NOT NULL DEFAULT 0 CHECK (balance >= 0),

    account_type ENUM('SAVINGS', 'CURRENT') NOT NULL,
    dob DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (bank_id) REFERENCES bank(bank_id),
    FOREIGN KEY (branch_id) REFERENCES branch(branch_id)
);

CREATE TABLE gateway (
    gateway_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    type ENUM('UPI', 'NET_BANKING', 'BANK_TRANSFER') NOT NULL
);

CREATE TABLE gateway_txn (
    gtw_txn_id VARCHAR(50) PRIMARY KEY,

    idempotency_key VARCHAR(100) UNIQUE NOT NULL,

    gateway_id INT NOT NULL,
    sender_account_id INT NOT NULL,
    receiver_account_id INT NOT NULL,

    amount DECIMAL(15,2) NOT NULL CHECK (amount > 0),

    status ENUM('INITIATED', 'PENDING', 'SUCCESS', 'FAILED','ROLLEDBACK') NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (gateway_id) REFERENCES gateway(gateway_id),
    FOREIGN KEY (sender_account_id) REFERENCES accounts(account_id),
    FOREIGN KEY (receiver_account_id) REFERENCES accounts(account_id)
);

CREATE TABLE transaction_log (
    txn_id INT PRIMARY KEY AUTO_INCREMENT,

    gtw_txn_id VARCHAR(50) NOT NULL,

    account_id INT NOT NULL,
    entry_type ENUM('DEBIT', 'CREDIT') NOT NULL,

    amount DECIMAL(15,2) NOT NULL CHECK (amount > 0),

    status ENUM('SUCCESS', 'FAILED','PENDING') NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (gtw_txn_id) REFERENCES gateway_txn(gtw_txn_id),
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
);

CREATE TABLE gateway_logs (
    log_id INT PRIMARY KEY AUTO_INCREMENT,

    gtw_txn_id VARCHAR(50),
    gateway_id INT,

    amount DECIMAL(15,2),
    status ENUM('SUCCESS','FAILED','PENDING') not NULL,

    log_timestamp TIMESTAMP,

    INDEX (gtw_txn_id)
);

CREATE TABLE reconciliation (
    recon_id INT PRIMARY KEY AUTO_INCREMENT,

    gtw_txn_id VARCHAR(50),

    gateway_status VARCHAR(20),
    internal_status VARCHAR(20),

    gateway_amount DECIMAL(15,2),
    internal_amount DECIMAL(15,2),

    result ENUM(
        'MATCH',
        'MISMATCH',
        'MISSING_INTERNAL',
        'MISSING_GATEWAY',
        'AMOUNT_MISMATCH'
    ),

    action_taken VARCHAR(100),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX (gtw_txn_id)
);

CREATE TABLE reconciliation_jobs (
    job_id INT PRIMARY KEY AUTO_INCREMENT,

    status ENUM('RUNNING', 'SUCCESS', 'FAILED') NOT NULL,

    message TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL
);

CREATE INDEX idx_txn_gtw ON transaction_log(gtw_txn_id);
CREATE INDEX idx_gateway_logs_time ON gateway_logs(log_timestamp);
CREATE INDEX idx_recon_time ON reconciliation(created_at);