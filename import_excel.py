import os
import sqlite3
import pandas as pd

def import_data():
    excel_path = os.path.join(os.path.dirname(__file__), 'data.xlsx')
    db_path = os.path.join(os.path.dirname(__file__), 'database', 'supermarket.db')

    if not os.path.exists(excel_path):
        print(f"Error: Excel file not found at {excel_path}")
        return

    df = pd.read_excel(excel_path)
    print("Reading excel data:")
    print(df)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Category and image mapping helper
    category_map = {
        'nycil powder': ('Personal Care', '/static/product_images/nycil_powder.svg'),
        'loreal foam cleanser': ('Personal Care', '/static/product_images/loreal_cleanser.svg'),
        'harpic cleaner': ('Household Care', '/static/product_images/harpic_cleaner.svg'),
    }

    inserted_count = 0
    updated_count = 0

    for idx, row in df.iterrows():
        product_name = str(row['product_name']).strip()
        barcode = str(row['barcode_id']).strip()
        price = float(row['price'])
        
        lower_name = product_name.lower()
        category, image_path = category_map.get(
            lower_name, 
            ('General', '/static/product_images/soap.svg')
        )
        stock_quantity = int(row.get('stock_quantity', 100))

        cursor.execute("SELECT id FROM products WHERE barcode = ?", (barcode,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute('''
                UPDATE products 
                SET product_name = ?, category = ?, price = ?, stock_quantity = ?, image_path = ?
                WHERE barcode = ?
            ''', (product_name, category, price, stock_quantity, image_path, barcode))
            updated_count += 1
            print(f"Updated product: {product_name} (Barcode: {barcode})")
        else:
            cursor.execute('''
                INSERT INTO products (barcode, product_name, category, price, stock_quantity, image_path)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (barcode, product_name, category, price, stock_quantity, image_path))
            inserted_count += 1
            print(f"Inserted product: {product_name} (Barcode: {barcode})")

    conn.commit()
    conn.close()
    print(f"\nImport finished successfully! Inserted: {inserted_count}, Updated: {updated_count}")

if __name__ == '__main__':
    import_data()
