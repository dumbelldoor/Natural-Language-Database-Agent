-- Drop tables if they exist to keep things clean
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

-- 1. Customers Table
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    registration_date DATE DEFAULT CURRENT_DATE
);

-- 2. Products Table
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    price DECIMAL(10, 2) NOT NULL,
    stock_quantity INT DEFAULT 0
);

-- 3. Orders Table
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(customer_id),
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending'
);

-- 4. Order Items Table (For complex joins)
CREATE TABLE order_items (
    item_id SERIAL PRIMARY KEY,
    order_id INT REFERENCES orders(order_id),
    product_id INT REFERENCES products(product_id),
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL
);

-- --- INSERT DUMMY DATA ---

INSERT INTO customers (first_name, last_name, email, registration_date) VALUES
('Alice', 'Smith', 'alice@example.com', '2025-01-15'),
('Bob', 'Johnson', 'bob@example.com', '2025-02-20'),
('Charlie', 'Brown', 'charlie@example.com', '2025-03-10');

INSERT INTO products (product_name, category, price, stock_quantity) VALUES
('Wireless Mouse', 'Electronics', 25.99, 150),
('Mechanical Keyboard', 'Electronics', 89.50, 75),
('Coffee Mug', 'Home', 12.00, 300),
('Desk Lamp', 'Home', 45.00, 40);

INSERT INTO orders (customer_id, order_date, status) VALUES
(1, '2026-02-20 10:30:00', 'shipped'),
(2, '2026-02-21 14:15:00', 'pending'),
(1, '2026-02-22 09:00:00', 'processing');

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
(1, 1, 1, 25.99),
(1, 3, 2, 12.00),
(2, 2, 1, 89.50),
(3, 4, 1, 45.00);
