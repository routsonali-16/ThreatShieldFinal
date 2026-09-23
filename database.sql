CREATE DATABASE IF NOT EXISTS threatshieldai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE threatshieldai;
CREATE TABLE IF NOT EXISTS scan_cases (id INT AUTO_INCREMENT PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, input_type VARCHAR(30), input_value TEXT, risk_score INT, risk_level VARCHAR(20));
CREATE TABLE IF NOT EXISTS source_registry (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(120), url VARCHAR(255), source_type VARCHAR(50), notes TEXT);
INSERT INTO source_registry(name,url,source_type,notes) VALUES
('Reserve Bank of India','https://www.rbi.org.in/','regulator','Official RBI website'),
('TransUnion CIBIL','https://www.cibil.com/','credit-bureau','Official credit information source'),
('RBI Sachet','https://sachet.rbi.org.in/','reporting','Official RBI portal');
