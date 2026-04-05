-- Clean up old tables
DROP TABLE IF EXISTS product_reviews CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS subcategories CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS suppliers CASCADE;
DROP TABLE IF EXISTS employees CASCADE;
DROP TABLE IF EXISTS departments CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ==========================================
-- 1. COMPLEX DDL SCHEMA CREATION
-- ==========================================

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(150) UNIQUE,
    phone_number VARCHAR(20),
    date_of_birth DATE,
    country VARCHAR(50),
    signup_date TIMESTAMP,
    is_active BOOLEAN,
    lifetime_value DECIMAL(12, 2) DEFAULT 0.00
);

CREATE TABLE departments (
    department_id SERIAL PRIMARY KEY,
    department_name VARCHAR(100),
    budget DECIMAL(15, 2)
);

CREATE TABLE employees (
    employee_id SERIAL PRIMARY KEY,
    department_id INT REFERENCES departments(department_id),
    manager_id INT REFERENCES employees(employee_id),
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    hire_date DATE,
    salary DECIMAL(12, 2)
);

CREATE TABLE suppliers (
    supplier_id SERIAL PRIMARY KEY,
    company_name VARCHAR(150),
    contact_email VARCHAR(150),
    contact_phone VARCHAR(20),
    country VARCHAR(50)
);

CREATE TABLE categories (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(100)
);

CREATE TABLE subcategories (
    subcategory_id SERIAL PRIMARY KEY,
    category_id INT REFERENCES categories(category_id),
    subcategory_name VARCHAR(100)
);

CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    subcategory_id INT REFERENCES subcategories(subcategory_id),
    supplier_id INT REFERENCES suppliers(supplier_id),
    product_name VARCHAR(200),
    description TEXT,
    cost_price DECIMAL(10, 2),
    retail_price DECIMAL(10, 2),
    stock_quantity INT,
    weight_kg DECIMAL(8, 2),
    is_discontinued BOOLEAN
);

CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    order_date TIMESTAMP,
    shipping_date TIMESTAMP,
    status VARCHAR(50),
    shipping_country VARCHAR(50),
    tracking_number VARCHAR(100),
    total_amount DECIMAL(12, 2)
);

CREATE TABLE order_items (
    item_id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(order_id),
    product_id INT REFERENCES products(product_id),
    quantity INT,
    unit_price DECIMAL(10, 2),
    discount DECIMAL(5, 2) DEFAULT 0.00
);

CREATE TABLE payments (
    payment_id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(order_id),
    payment_date TIMESTAMP,
    payment_method VARCHAR(50),
    amount DECIMAL(12, 2),
    is_successful BOOLEAN
);

CREATE TABLE product_reviews (
    review_id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(product_id),
    user_id INT REFERENCES users(user_id),
    rating INT CHECK (rating >= 1 AND rating <= 5),
    review_text TEXT,
    review_date TIMESTAMP
);

-- ==========================================
-- 2. MASSIVE RANDOMIZED DML DATA GENERATION
-- ==========================================

-- A. Insert 15,000 Users with highly randomized phones and dates
INSERT INTO users (first_name, last_name, email, phone_number, date_of_birth, country, signup_date, is_active)
SELECT 
    chr(trunc(random() * 26)::int + 65) || 'user_first_' || id, 
    chr(trunc(random() * 26)::int + 65) || 'user_last_' || id, 
    'user_' || id || '_' || trunc(random()*9999) || '@example.com', 
    '+' || trunc(random() * 90 + 10)::text || ' ' || trunc(random() * 900000000 + 100000000)::text,
    CURRENT_DATE - (random() * 365 * 60 + 365 * 18)::integer, -- Age 18 to 78
    (ARRAY['USA', 'Canada', 'UK', 'Germany', 'Australia', 'India', 'Japan', 'Brazil', 'France'])[trunc(random() * 9 + 1)],
    CURRENT_TIMESTAMP - (trunc(random() * 365 * 5)::text || ' days')::interval,
    random() > 0.15
FROM generate_series(1, 15000) AS id;

-- B. Insert Departments & Employees
INSERT INTO departments (department_name, budget) VALUES 
('Engineering', 5000000.00), ('Sales', 3000000.00), ('Marketing', 2000000.00), ('HR', 1000000.00), ('Support', 1500000.00);

-- Insert 1,000 Employees
INSERT INTO employees (department_id, manager_id, first_name, last_name, hire_date, salary)
SELECT 
    (random() * 4 + 1)::integer,
    NULL, -- We will update managers next
    'Emp_First_' || id,
    'Emp_Last_' || id,
    CURRENT_DATE - (random() * 365 * 10)::integer,
    (random() * 80000 + 40000)::numeric(12,2)
FROM generate_series(1, 1000) AS id;

-- Assign random managers (about 10% are managers)
UPDATE employees SET manager_id = (random() * 99 + 1)::integer WHERE employee_id > 100;

-- C. Insert 500 Suppliers
INSERT INTO suppliers (company_name, contact_email, contact_phone, country)
SELECT 
    'Supplier_Corp_' || id,
    'contact@supplier' || id || '.com',
    '+' || trunc(random() * 90 + 10)::text || ' ' || trunc(random() * 900000000 + 100000000)::text,
    (ARRAY['China', 'USA', 'Vietnam', 'Mexico', 'Taiwan', 'Germany'])[trunc(random() * 6 + 1)]
FROM generate_series(1, 500) AS id;

-- D. Categories and Subcategories
INSERT INTO categories (category_name) VALUES 
('Electronics'), ('Apparel'), ('Home & Garden'), ('Sports & Outdoors'), ('Health & Beauty');

INSERT INTO subcategories (category_id, subcategory_name)
SELECT 
    (id % 5) + 1,
    'Subcategory_' || id
FROM generate_series(1, 25) AS id;

-- E. Insert 10,000 Products with complex pricing logic
INSERT INTO products (subcategory_id, supplier_id, product_name, description, cost_price, retail_price, stock_quantity, weight_kg, is_discontinued)
SELECT 
    (random() * 24 + 1)::integer,
    (random() * 499 + 1)::integer,
    'Product_Model_' || chr(trunc(random() * 26)::int + 65) || id,
    'This is a randomly generated description for product ' || id,
    (random() * 400 + 10)::numeric(10,2),
    0, -- Placeholder
    (random() * 1500)::integer,
    (random() * 20 + 0.1)::numeric(8,2),
    random() > 0.95
FROM generate_series(1, 10000) AS id;

-- Set retail price to cost price + random markup (20% to 150%)
UPDATE products SET retail_price = cost_price * (1.2 + random() * 1.3);

-- F. Insert 50,000 Orders
INSERT INTO orders (user_id, order_date, shipping_date, status, shipping_country, tracking_number, total_amount)
SELECT 
    (random() * 14999 + 1)::integer,
    CURRENT_TIMESTAMP - (trunc(random() * 365 * 3)::text || ' days')::interval,
    NULL,
    CASE 
        WHEN random() > 0.4 THEN 'Delivered'
        WHEN random() > 0.2 THEN 'Shipped'
        WHEN random() > 0.1 THEN 'Processing'
        ELSE 'Cancelled'
    END,
    (ARRAY['USA', 'Canada', 'UK', 'Germany', 'Australia', 'India', 'Japan', 'Brazil', 'France'])[trunc(random() * 9 + 1)],
    'TRK' || trunc(random() * 9999999999),
    0 -- Placeholder
FROM generate_series(1, 50000) AS id;

-- Set valid shipping dates for shipped/delivered orders
UPDATE orders SET shipping_date = order_date + (trunc(random() * 10)::text || ' days')::interval WHERE status IN ('Shipped', 'Delivered');

-- G. Insert 150,000 Order Items
INSERT INTO order_items (order_id, product_id, quantity, unit_price, discount)
SELECT 
    (random() * 49999 + 1)::integer,
    (random() * 9999 + 1)::integer,
    (random() * 4 + 1)::integer,
    (random() * 500 + 10)::numeric(10,2), -- Rough randomized retail price
    CASE WHEN random() > 0.8 THEN (random() * 0.3)::numeric(5,2) ELSE 0.00 END
FROM generate_series(1, 150000) AS id;

-- H. Update Orders Total Amount and Users Lifetime Value (Optimized with Bulk Joins)
UPDATE orders o
SET total_amount = agg.total
FROM (
    SELECT order_id, COALESCE(SUM(quantity * unit_price * (1 - discount)), 0) as total
    FROM order_items
    GROUP BY order_id
) agg
WHERE o.order_id = agg.order_id;

UPDATE users u
SET lifetime_value = agg.total
FROM (
    SELECT user_id, COALESCE(SUM(total_amount), 0) as total
    FROM orders
    WHERE status = 'Delivered'
    GROUP BY user_id
) agg
WHERE u.user_id = agg.user_id;

-- I. Insert 75,000 Payments
INSERT INTO payments (order_id, payment_date, payment_method, amount, is_successful)
SELECT 
    order_id,
    order_date + (trunc(random() * 2)::text || ' days')::interval,
    (ARRAY['Credit Card', 'PayPal', 'Crypto', 'Bank Transfer'])[trunc(random() * 4 + 1)],
    total_amount,
    true
FROM orders
WHERE status != 'Cancelled';

-- Add some failed/cancelled payments
INSERT INTO payments (order_id, payment_date, payment_method, amount, is_successful)
SELECT 
    order_id,
    order_date + (trunc(random() * 1)::text || ' days')::interval,
    'Credit Card',
    total_amount,
    false
FROM orders
WHERE status = 'Cancelled';

-- J. Insert 40,000 Product Reviews
INSERT INTO product_reviews (product_id, user_id, rating, review_text, review_date)
SELECT 
    (random() * 9999 + 1)::integer,
    (random() * 14999 + 1)::integer,
    (random() * 4 + 1)::integer, -- 1 to 5 stars
    'This product was ' || (ARRAY['amazing', 'terrible', 'okay', 'great', 'mediocre'])[trunc(random() * 5 + 1)] || '. Overall experience was exactly ' || id,
    CURRENT_TIMESTAMP - (trunc(random() * 365 * 2)::text || ' days')::interval
FROM generate_series(1, 40000) AS id;

-- Vacuum analyze to optimize the new massive tables for querying
VACUUM ANALYZE;
