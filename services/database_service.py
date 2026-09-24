import os
import sqlite3
import json
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'database')
DB_PATH = os.path.join(DB_DIR, 'supermarket.db')

def get_db_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT UNIQUE NOT NULL,
            product_name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            stock_quantity INTEGER NOT NULL DEFAULT 0,
            image_path TEXT DEFAULT ''
        )
    ''')

    # Create bills table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_number TEXT UNIQUE NOT NULL,
            timestamp DATETIME NOT NULL,
            products_json TEXT NOT NULL,
            subtotal REAL NOT NULL,
            gst_percent REAL NOT NULL,
            gst_amount REAL NOT NULL,
            discount REAL NOT NULL DEFAULT 0.0,
            grand_total REAL NOT NULL,
            payment_status TEXT DEFAULT 'Completed',
            payment_method TEXT DEFAULT 'UPI / QR'
        )
    ''')

    # Safe migration: Add missing columns if they don't exist yet
    cursor.execute("PRAGMA table_info(products)")
    existing_cols = [col['name'] for col in cursor.fetchall()]

    new_cols = [
        ('discount_percent', 'REAL DEFAULT 0.0'),
        ('min_stock_threshold', 'INTEGER DEFAULT 15'),
        ('max_stock_capacity', 'INTEGER DEFAULT 200'),
        ('expiry_date', "TEXT DEFAULT '2026-12-31'"),
        ('units_sold', 'INTEGER DEFAULT 0'),
        ('revenue', 'REAL DEFAULT 0.0'),
        ('transactions_count', 'INTEGER DEFAULT 0')
    ]

    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}")

    cursor.execute("PRAGMA table_info(bills)")
    existing_bill_cols = [col['name'] for col in cursor.fetchall()]
    if 'payment_status' not in existing_bill_cols:
        cursor.execute("ALTER TABLE bills ADD COLUMN payment_status TEXT DEFAULT 'Completed'")
    if 'payment_method' not in existing_bill_cols:
        cursor.execute("ALTER TABLE bills ADD COLUMN payment_method TEXT DEFAULT 'UPI / QR'")

    # Check if products table is empty and seed default sample data
    cursor.execute('SELECT COUNT(*) as count FROM products')
    row_count = cursor.fetchone()['count']

    if row_count == 0:
        sample_products = [
            ('8901234567890', 'Milk', 'Dairy', 30.00, 100, '/static/product_images/milk.svg'),
            ('8901234567891', 'Bread', 'Bakery', 40.00, 50, '/static/product_images/bread.svg'),
            ('8901234567892', 'Biscuits', 'Snacks', 20.00, 150, '/static/product_images/biscuits.svg'),
            ('8901234567893', 'Apple Juice 1L', 'Beverages', 65.00, 80, '/static/product_images/apple_juice.svg'),
            ('8901234567894', 'Dark Chocolate 100g', 'Confectionery', 85.00, 120, '/static/product_images/chocolate.svg'),
            ('8901234567895', 'Organic Rice 1kg', 'Grains', 110.00, 60, '/static/product_images/rice.svg'),
            ('8901234567896', 'Bath Soap Pack', 'Personal Care', 45.00, 200, '/static/product_images/soap.svg'),
            ('8901234567897', 'Shampoo 200ml', 'Personal Care', 140.00, 75, '/static/product_images/shampoo.svg'),
            ('8901234567898', 'Mineral Water 1L', 'Beverages', 20.00, 300, '/static/product_images/water.svg'),
            ('8901542001253', 'Nycil Powder', 'Personal Care', 155.00, 100, '/static/product_images/nycil_powder.svg'),
            ('8994993016549', 'Loreal Foam Cleanser', 'Personal Care', 229.00, 100, '/static/product_images/loreal_cleanser.svg'),
            ('8901396151005', 'Harpic Cleaner', 'Household Care', 110.00, 100, '/static/product_images/harpic_cleaner.svg'),
        ]
        cursor.executemany('''
            INSERT INTO products (barcode, product_name, category, price, stock_quantity, image_path)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_products)

    conn.commit()
    conn.close()

    # Automatically seed historical bills for previous days
    seed_historical_bills()

def format_product_dict(row):
    d = dict(row)
    current_stock = d.get('stock_quantity', 0)
    min_stock = d.get('min_stock_threshold') or 15
    
    if current_stock <= 0:
        status = 'Low Stock'
    elif current_stock <= min_stock:
        status = 'Low Stock'
    else:
        status = 'In Stock'

    d.update({
        "id": str(d.get('id', d.get('barcode', ''))),
        "name": d.get('product_name', ''),
        "product_name": d.get('product_name', ''),
        "category": d.get('category', 'General'),
        "price": float(d.get('price', 0.0)),
        "unitsSold": int(d.get('units_sold') or 0),
        "revenue": float(d.get('revenue') or 0.0),
        "transactionsCount": int(d.get('transactions_count') or 0),
        "currentStock": current_stock,
        "stock_quantity": current_stock,
        "minStockThreshold": min_stock,
        "maxStockCapacity": int(d.get('max_stock_capacity') or 200),
        "expiryDate": d.get('expiry_date') or '2026-12-31',
        "status": status,
        "discountPercent": float(d.get('discount_percent') or 0.0),
        "turnoverRate": 4.2,
        "imagePlaceholder": d.get('image_path', '')
    })
    return d

def get_product_by_barcode(barcode):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE barcode = ?', (str(barcode).strip(),))
    row = cursor.fetchone()
    conn.close()
    if row:
        return format_product_dict(row)
    return None

def get_all_products():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products ORDER BY id ASC')
    rows = cursor.fetchall()
    conn.close()
    return [format_product_dict(r) for r in rows]

def get_all_bills():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM bills ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()

    formatted_bills = []
    for r in rows:
        d = dict(r)
        try:
            products_list = json.loads(d.get('products_json', '[]'))
        except Exception:
            products_list = []
        
        items_count = sum(p.get('quantity', 1) for p in products_list)
        product_names = [p.get('product_name', 'Item') for p in products_list]
        
        formatted_bills.append({
            "id": d.get('bill_number', f"BILL-{d.get('id')}"),
            "timestamp": d.get('timestamp', ''),
            "customerName": "Walk-in Customer",
            "itemsCount": items_count,
            "productNames": product_names,
            "totalAmount": float(d.get('grand_total', 0.0)),
            "paymentMethod": d.get('payment_method', 'UPI / QR'),
            "status": d.get('payment_status', 'Completed'),
            "counterId": "POS Counter-01"
        })
    return formatted_bills

def update_product_price_and_discount(product_id, price, discount_percent):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE products
        SET price = ?, discount_percent = ?
        WHERE id = ? OR barcode = ?
    ''', (float(price), float(discount_percent), str(product_id), str(product_id)))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def restock_product(product_id, quantity):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE products
        SET stock_quantity = stock_quantity + ?
        WHERE id = ? OR barcode = ?
    ''', (int(quantity), str(product_id), str(product_id)))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def save_bill(bill_number, products_list, subtotal, gst_percent, gst_amount, discount, grand_total, payment_status='Pending', payment_method='UPI / QR'):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    products_json = json.dumps(products_list)
    
    cursor.execute('''
        INSERT INTO bills (bill_number, timestamp, products_json, subtotal, gst_percent, gst_amount, discount, grand_total, payment_status, payment_method)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (bill_number, now_str, products_json, subtotal, gst_percent, gst_amount, discount, grand_total, payment_status, payment_method))
    
    # Update product stock quantities, units_sold, revenue, and transaction_counts
    for p in products_list:
        barcode = p.get('barcode')
        qty = int(p.get('quantity', 1))
        item_price = float(p.get('price', 0.0))
        item_total = float(p.get('total', item_price * qty))
        if barcode:
            cursor.execute('''
                UPDATE products
                SET stock_quantity = MAX(0, stock_quantity - ?),
                    units_sold = units_sold + ?,
                    revenue = revenue + ?,
                    transactions_count = transactions_count + 1
                WHERE barcode = ? OR id = ?
            ''', (qty, qty, item_total, str(barcode), str(barcode)))
            
    conn.commit()
    conn.close()
    return {
        "bill_number": bill_number,
        "timestamp": now_str,
        "products": products_list,
        "subtotal": subtotal,
        "gst_percent": gst_percent,
        "gst_amount": gst_amount,
        "discount": discount,
        "grand_total": grand_total,
        "payment_status": payment_status,
        "payment_method": payment_method
    }

def mark_bill_paid(bill_number):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE bills
        SET payment_status = 'Completed'
        WHERE bill_number = ?
    ''', (bill_number,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def get_bill_by_number(bill_number):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM bills WHERE bill_number = ?', (bill_number,))
    row = cursor.fetchone()
    conn.close()
    if row:
        data = dict(row)
        data['products'] = json.loads(data['products_json'])
        return data
    return None

import random
from datetime import datetime, timedelta

def seed_historical_bills(force=False):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) as count FROM bills')
    bills_count = cursor.fetchone()['count']

    if bills_count >= 25 and not force:
        conn.close()
        return

    cursor.execute('SELECT barcode, product_name, category, price FROM products')
    products = [dict(r) for r in cursor.fetchall()]
    if not products:
        conn.close()
        return

    payment_methods = ['UPI / QR', 'Credit Card', 'Cash', 'Smart Wallet']
    today_dt = datetime(2026, 9, 24)

    # Generate 50 historical bills across past 30 days (1 to 30 days before today)
    for i in range(1, 51):
        days_ago = random.randint(1, 30)
        bill_date = today_dt - timedelta(days=days_ago, hours=random.randint(0, 12), minutes=random.randint(0, 59))
        date_str = bill_date.strftime('%Y-%m-%d %H:%M:%S')
        date_num_str = bill_date.strftime('%Y%m%d')
        bill_number = f"BILL-{date_num_str}-{1000 + i}"

        chosen_items = random.sample(products, k=random.randint(1, min(4, len(products))))
        products_list = []
        subtotal = 0.0

        for p in chosen_items:
            qty = random.randint(1, 3)
            price = float(p['price'])
            item_total = round(price * qty, 2)
            subtotal += item_total
            products_list.append({
                "barcode": p['barcode'],
                "product_name": p['product_name'],
                "category": p['category'],
                "price": price,
                "quantity": qty,
                "total": item_total
            })

        subtotal = round(subtotal, 2)
        gst_percent = 5.0
        gst_amount = round(subtotal * 0.05, 2)
        discount = round(random.choice([0.0, 5.0, 10.0, 15.0]), 2) if subtotal > 100 else 0.0
        grand_total = max(0.0, round(subtotal + gst_amount - discount, 2))
        payment_method = random.choice(payment_methods)

        products_json = json.dumps(products_list)
        cursor.execute('''
            INSERT OR IGNORE INTO bills (bill_number, timestamp, products_json, subtotal, gst_percent, gst_amount, discount, grand_total, payment_status, payment_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Completed', ?)
        ''', (bill_number, date_str, products_json, subtotal, gst_percent, gst_amount, discount, grand_total, payment_method))

        for item in products_list:
            cursor.execute('''
                UPDATE products
                SET units_sold = units_sold + ?,
                    revenue = revenue + ?,
                    transactions_count = transactions_count + 1
                WHERE barcode = ?
            ''', (item['quantity'], item['total'], item['barcode']))

    conn.commit()
    conn.close()


