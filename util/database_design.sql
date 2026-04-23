create database if not exists tre;
use tre;

create table banks (
    bank_id INT PRIMARY KEY AUTO_INCREMENT,
    bank_name VARCHAR(100),
    bank_code VARCHAR(20) UNIQUE,
    created_at TIMESTAMP
);

create table users (
    user_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100),
    email VARCHAR(100),
    phone VARCHAR(15),
    created_at TIMESTAMP
);

create table bank_accounts (
    account_id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    bank_id INT,
    account_number VARCHAR(30),
    ifsc_code VARCHAR(20),
    balance DECIMAL(12,2),
    created_at TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (bank_id) REFERENCES banks(bank_id)
);

create table gateways (
    gateway_id INT PRIMARY KEY AUTO_INCREMENT,
    gateway_name VARCHAR(50),  -- UPI, NetBanking, etc
    provider VARCHAR(50),      -- Razorpay, Paytm, etc
    created_at TIMESTAMP
);

create table transactions (
    txn_id VARCHAR(50) PRIMARY KEY,
    user_id INT,
    sender_account_id INT,
    receiver_account_id INT,
    amount DECIMAL(12,2),
    txn_type VARCHAR(20), -- debit/credit
    txn_time TIMESTAMP,
    status VARCHAR(20),   -- success/pending/failed
    gateway_id INT,

    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (gateway_id) REFERENCES gateways(gateway_id)
);

create table bank_transaction_logs (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    txn_id VARCHAR(50),
    bank_id INT,
    raw_data JSON,
    log_time TIMESTAMP,

    FOREIGN KEY (txn_id) REFERENCES transactions(txn_id),
    FOREIGN KEY (bank_id) REFERENCES banks(bank_id)
);

create table gateway_transaction_logs (
    log_id INT PRIMARY KEY AUTO_INCREMENT,
    txn_id VARCHAR(50),
    gateway_id INT,
    raw_data JSON,
    log_time TIMESTAMP,

    FOREIGN KEY (txn_id) REFERENCES transactions(txn_id)
);

create table reconciliation (
    recon_id INT PRIMARY KEY AUTO_INCREMENT,
    txn_id VARCHAR(50),
    bank_status VARCHAR(20),
    gateway_status VARCHAR(20),
    reconciliation_status VARCHAR(20), -- matched/mismatch/missing
    remarks VARCHAR(255),
    reconciled_at TIMESTAMP,

    FOREIGN KEY (txn_id) REFERENCES transactions(txn_id)
);

