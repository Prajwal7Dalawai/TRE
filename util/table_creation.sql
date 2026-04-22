create database ABC;
use ABC;

-- Table creations

-- User table
CREATE TABLE Users (
    user_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(50),
    dob DATE
);

-- accounts
CREATE TABLE Accounts (
    account_id VARCHAR(10) PRIMARY KEY,
    user_id VARCHAR(10),
    bank_name VARCHAR(50),
    ifsc_code VARCHAR(20),
    balance INT,
    FOREIGN KEY (user_id) REFERENCES Users(user_id)
);

-- UPI handles
CREATE TABLE UPI_Handles (
    upi_id VARCHAR(50) PRIMARY KEY,
    account_id VARCHAR(10),
    FOREIGN KEY (account_id) REFERENCES Accounts(account_id)
);

-- Transasctions
CREATE TABLE Transactions (
    txn_id INT AUTO_INCREMENT PRIMARY KEY,
    from_account VARCHAR(10),
    to_account VARCHAR(10),
    amount INT,
    status VARCHAR(20),
    reference_id VARCHAR(50) UNIQUE,
    txn_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_account) REFERENCES Accounts(account_id),
    FOREIGN KEY (to_account) REFERENCES Accounts(account_id)
);

-- Tranbsaction log
CREATE TABLE Transaction_Log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    txn_id INT,
    event_type VARCHAR(20),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    payer_balance_after INT,
    payee_balance_after INT,
    FOREIGN KEY (txn_id) REFERENCES Transactions(txn_id)
);

-- Gateway transaction
CREATE TABLE GatewayTransactions (
    gateway_txn_id VARCHAR(10) PRIMARY KEY,
    reference_id VARCHAR(50),
    amount INT,
    status VARCHAR(20),
    txn_time TIMESTAMP
);

-- Reconciliation
CREATE TABLE Reconciliation (
    recon_id INT AUTO_INCREMENT PRIMARY KEY,
    reference_id VARCHAR(50),
    status VARCHAR(20),
    reason VARCHAR(100)
);