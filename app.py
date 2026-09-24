import os
import base64
import random
import time
import logging
from datetime import datetime
import cv2
import numpy as np
from flask import Flask, render_template, request, jsonify

from services.database_service import (
    init_db,
    get_product_by_barcode,
    get_all_products,
    get_all_bills,
    update_product_price_and_discount,
    restock_product,
    save_bill,
    mark_bill_paid,
    get_bill_by_number
)
from services.yolo_detector import YOLODetector
from services.barcode_decoder import BarcodeDecoder, PYZBAR_AVAILABLE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global CORS Handler for Dashboard integration
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
    return response

# Initialize database
init_db()

# Initialize YOLO model ONCE at startup
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'best.pt')
yolo_detector = YOLODetector(model_path=MODEL_PATH)
barcode_decoder = BarcodeDecoder()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "online",
        "app": "BillSightAI",
        "model_loaded": yolo_detector.model_loaded,
        "gpu_available": yolo_detector.gpu_available,
        "pyzbar_available": PYZBAR_AVAILABLE,
        "database_connected": True
    })

@app.route('/api/products', methods=['GET'])
def list_products():
    products = get_all_products()
    return jsonify(products)

@app.route('/api/transactions', methods=['GET', 'OPTIONS'])
def list_transactions():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    transactions = get_all_bills()
    return jsonify(transactions)

@app.route('/api/products/<product_id>/price', methods=['PATCH', 'PUT', 'POST', 'OPTIONS'])
def update_price(product_id):
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        data = request.get_json(force=True) or {}
        price = float(data.get('price', 0))
        discount_percent = float(data.get('discountPercent', data.get('discount_percent', 0)))
        success = update_product_price_and_discount(product_id, price, discount_percent)
        return jsonify({"success": success, "productId": product_id, "price": price, "discountPercent": discount_percent})
    except Exception as e:
        logger.error(f"Error in update_price: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/purchase-orders', methods=['POST', 'OPTIONS'])
def purchase_orders():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        data = request.get_json(force=True) or {}
        product_id = data.get('productId') or data.get('product_id')
        quantity = int(data.get('quantity', 0))
        if not product_id or quantity <= 0:
            return jsonify({"success": False, "message": "Invalid productId or quantity"}), 400
        success = restock_product(product_id, quantity)
        return jsonify({"success": success, "productId": product_id, "quantity": quantity})
    except Exception as e:
        logger.error(f"Error in purchase_orders: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/detect', methods=['POST'])
def detect_barcode():
    try:
        data = request.get_json(force=True)
        if not data or 'image' not in data:
            return jsonify({"success": False, "barcode_detected": False, "message": "No image payload provided"}), 400

        image_data = data['image']
        # Strip Base64 header if present (e.g. data:image/jpeg;base64,...)
        if ',' in image_data:
            image_data = image_data.split(',')[1]

        image_bytes = base64.b64decode(image_data)
        np_arr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if frame is None:
            return jsonify({"success": False, "barcode_detected": False, "message": "Invalid frame data"}), 400

        # Step 1: Run YOLO detection for barcode ROI
        detection_result = yolo_detector.detect(frame)
        bbox = detection_result['bounding_box'] if detection_result else None
        conf = detection_result['confidence'] if detection_result else 0.0
        class_name = detection_result['class_name'] if detection_result else "barcode"

        # Step 2: Decode barcode using pyzbar / OpenCV
        decoded_barcode = barcode_decoder.decode(frame, bbox=bbox)

        if not decoded_barcode:
            # If AI bounding box was detected or fallback ROI was generated, but decoding failed
            if detection_result:
                return jsonify({
                    "success": False,
                    "barcode_detected": False,
                    "bounding_box": bbox,
                    "confidence": conf,
                    "class_name": class_name,
                    "message": "Barcode region located, but barcode value could not be decoded. Position product clearly."
                })
            else:
                return jsonify({
                    "success": False,
                    "barcode_detected": False,
                    "message": "No barcode detected. Please position the product clearly."
                })

        # Step 3: Match barcode with database product
        product = get_product_by_barcode(decoded_barcode)

        # Ensure we send valid bounding box (if not produced by YOLO, estimate center ROI)
        if not bbox:
            h, w = frame.shape[:2]
            bbox = {
                "x1": int(w * 0.2),
                "y1": int(h * 0.25),
                "x2": int(w * 0.8),
                "y2": int(h * 0.75)
            }
            conf = 0.90

        if product:
            return jsonify({
                "success": True,
                "barcode_detected": True,
                "barcode": decoded_barcode,
                "product_found": True,
                "product": product,
                "confidence": conf,
                "bounding_box": bbox,
                "class_name": class_name
            })
        else:
            return jsonify({
                "success": False,
                "barcode_detected": True,
                "product_found": False,
                "barcode": decoded_barcode,
                "confidence": conf,
                "bounding_box": bbox,
                "class_name": class_name,
                "message": f"Barcode '{decoded_barcode}' detected, but the product is not available in the database."
            })

    except Exception as e:
        logger.error(f"Error in /api/detect: {e}", exc_info=True)
        return jsonify({"success": False, "barcode_detected": False, "message": f"Server error: {str(e)}"}), 500

@app.route('/api/bill/generate', methods=['POST', 'OPTIONS'])
def generate_bill():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        data = request.get_json(force=True) or {}
        products_list = data.get('products', [])
        subtotal = float(data.get('subtotal', 0.0))
        gst_percent = float(data.get('gst_percent', 5.0))
        discount = float(data.get('discount', 0.0))

        if not products_list or subtotal <= 0:
            return jsonify({"success": False, "message": "Cannot generate bill with empty or 0 amount cart"}), 400

        gst_amount = round(subtotal * (gst_percent / 100.0), 2)
        grand_total = max(0.0, round(subtotal + gst_amount - discount, 2))

        # Generate unique bill number
        date_str = datetime.now().strftime('%Y%m%d')
        rand_str = f"{random.randint(1000, 9999)}"
        bill_number = f"BILL-{date_str}-{rand_str}"

        bill_record = save_bill(
            bill_number=bill_number,
            products_list=products_list,
            subtotal=subtotal,
            gst_percent=gst_percent,
            gst_amount=gst_amount,
            discount=discount,
            grand_total=grand_total,
            payment_status='Pending',
            payment_method='UPI / QR'
        )

        # Build UPI payment URL and quickchart QR image URL
        upi_url = f"upi://pay?pa=billsight@upi&pn=BillSightAI&am={grand_total:.2f}&tn=Payment+for+{bill_number}"
        qr_image_url = f"https://quickchart.io/qr?text={upi_url}&size=220&margin=1"

        return jsonify({
            "success": True,
            "bill": bill_record,
            "upi_url": upi_url,
            "qr_image_url": qr_image_url
        })
    except Exception as e:
        logger.error(f"Error in /api/bill/generate: {e}", exc_info=True)
        return jsonify({"success": False, "message": f"Failed to generate bill: {str(e)}"}), 500

@app.route('/api/bill/<bill_number>/pay', methods=['POST', 'GET', 'OPTIONS'])
def pay_bill(bill_number):
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        success = mark_bill_paid(bill_number)
        if success:
            bill = get_bill_by_number(bill_number)
            return jsonify({
                "success": True,
                "message": f"Bill {bill_number} marked as PAID successfully",
                "payment_status": "Completed",
                "bill": bill
            })
        else:
            return jsonify({"success": False, "message": f"Bill {bill_number} not found"}), 404
    except Exception as e:
        logger.error(f"Error in pay_bill: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    # Default port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)


