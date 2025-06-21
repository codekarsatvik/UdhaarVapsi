-- Create table
CREATE TABLE test_data (
    id SERIAL PRIMARY KEY,
    user_name VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert test data
INSERT INTO test_data (user_name) VALUES 
    ('Alice'), 
    ('Bob'), 
    ('Charlie');

-- Update table
UPDATE test_data 
SET user_name = 'Alice Smith' 
WHERE id = 1;

-- Create materialized view
CREATE MATERIALIZED VIEW test_data_summary AS
SELECT 
    user_name, 
    COUNT(*) OVER() AS total_users
FROM test_data;