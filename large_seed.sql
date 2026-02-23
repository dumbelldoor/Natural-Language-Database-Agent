-- Clean up old tables
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- 1. Users Table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(100) UNIQUE,
    signup_date DATE,
    is_active BOOLEAN
);

-- 2. Categories Table
CREATE TABLE categories (
    category_id SERIAL PRIMARY KEY,
    category_name VARCHAR(100)
);

-- 3. Products Table
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    category_id INT REFERENCES categories(category_id),
    product_name VARCHAR(150),
    price DECIMAL(10, 2),
    stock INT
);

-- 4. Orders Table
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    order_date TIMESTAMP,
    total_amount DECIMAL(12, 2),
    status VARCHAR(20)
);

-- 5. Order Items Table
CREATE TABLE order_items (
    item_id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(order_id),
    product_id INT REFERENCES products(product_id),
    quantity INT,
    unit_price DECIMAL(10, 2)
);

-- --- GENERATE MASSIVE DUMMY DATA ---

-- Insert 10,000 Users
INSERT INTO users (first_name, last_name, email, signup_date, is_active)
SELECT 
    'UserFirst' || id, 
    'UserLast' || id, 
    'user' || id || '@testdomain.com', 
    CURRENT_DATE - (random() * 365 * 5)::integer,
    random() > 0.1
FROM generate_series(1, 10000) AS id;

-- Insert Categories
INSERT INTO categories (category_name) VALUES 
('Electronics'), ('Clothing'), ('Home & Kitchen'), ('Books'), ('Sports Equipment');

-- Insert 5,000 Products
INSERT INTO products (category_id, product_name, price, stock)
SELECT 
    (random() * 4 + 1)::integer,
    'Product_' || id,
    (random() * 990 + 10)::numeric(10,2),
    (random() * 1000)::integer
FROM generate_series(1, 5000) AS id;

-- Insert 25,000 Orders
INSERT INTO orders (user_id, order_date, total_amount, status)
SELECT 
    (random() * 9999 + 1)::integer,
    CURRENT_TIMESTAMP - (random() * 365 * 2 || ' days')::interval,
    (random() * 500 + 50)::numeric(12,2),
    CASE 
        WHEN random() > 0.3 THEN 'Delivered'
        WHEN random() > 0.1 THEN 'Shipped'
        ELSE 'Pending'
    END
FROM generate_series(1, 25000) AS id;

-- Insert 60,000 Order Items
INSERT INTO order_items (order_id, product_id, quantity, unit_price)
SELECT 
    (random() * 24999 + 1)::integer,
    (random() * 4999 + 1)::integer,
    (random() * 5 + 1)::integer,
    (random() * 100 + 10)::numeric(10,2)
FROM generate_series(1, 60000) AS id;
