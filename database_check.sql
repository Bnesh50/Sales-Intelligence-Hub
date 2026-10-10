USE sales_management;

-- 1. Verify database
SELECT DATABASE() AS current_database;

-- 2. List tables
SHOW TABLES;

-- 3. Check branches
SELECT * FROM branches;

-- 4. Check customer sales
SELECT * FROM customer_sales;

-- 5. Check payment splits
SELECT * FROM payment_splits;

-- 6. Check users
SELECT user_id, username, branch_id, role, email
FROM users;

-- 7. Verify sales count
SELECT COUNT(*) AS total_sales
FROM customer_sales;

-- 8. Verify total gross sales
SELECT COALESCE(SUM(gross_sales), 0) AS total_gross_sales
FROM customer_sales;

-- 9. Verify total received amount
SELECT COALESCE(SUM(received_amount), 0) AS total_received_amount
FROM customer_sales;

-- 10. Verify total pending amount
SELECT COALESCE(SUM(pending_amount), 0) AS total_pending_amount
FROM customer_sales;

-- 11. Verify sale status
SELECT status, COUNT(*) AS sale_count
FROM customer_sales
GROUP BY status;

-- 12. Verify branch-wise sales
SELECT
    b.branch_name,
    COUNT(cs.sale_id) AS total_sales,
    COALESCE(SUM(cs.gross_sales), 0) AS total_gross_sales
FROM branches b
LEFT JOIN customer_sales cs
    ON b.branch_id = cs.branch_id
GROUP BY b.branch_id, b.branch_name
ORDER BY total_gross_sales DESC;

-- 13. Verify payment methods
SELECT
    payment_method,
    COUNT(*) AS payment_count,
    COALESCE(SUM(amount_paid), 0) AS total_amount
FROM payment_splits
GROUP BY payment_method
ORDER BY total_amount DESC;

-- 14. Verify split payments by sale
SELECT
    sale_id,
    COUNT(*) AS payment_count,
    COALESCE(SUM(amount_paid), 0) AS total_paid
FROM payment_splits
GROUP BY sale_id
ORDER BY sale_id;

-- 15. Verify trigger
SHOW TRIGGERS FROM sales_management;
