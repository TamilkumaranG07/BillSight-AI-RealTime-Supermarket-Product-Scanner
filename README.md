# BillSightAI — Intelligent Supermarket Billing System

> **College Final-Year AI Project**  
> An end-to-end, production-quality AI-powered supermarket billing web application. Live webcam frames are processed by a Python backend, bounding boxes are detected via a trained YOLOv8 model, decoded via OpenCV / Pyzbar, matched against an SQLite database, and automatically populated into a real-time interactive cart.

---

## 🌟 Key Features

- **Flat White & Yellow UI Theme**: Clean, professional supermarket cashier dashboard built with vanilla CSS3 and Bootstrap 5 (strictly flat colors — zero gradients, glassmorphism, or glow effects).
- **Live Product Scanner**: Webcam video feed with real-time bounding box canvas overlay (yellow bounding box, detected class, confidence %), camera selector, auto-scan mode with 3-second cooldown logic to prevent duplicate cart additions.
- **YOLOv8 Detection**: Loads PyTorch model `models/best.pt` once on server startup. Automatically utilizes CUDA GPU acceleration when available, with CPU and OpenCV contour fallback.
- **Robust Barcode Decoding**: Combines OpenCV preprocessing algorithms (Grayscale, CLAHE contrast enhancement, Otsu thresholding, sharpening) with `pyzbar` / `cv2.barcode.BarcodeDetector`.
- **SQLite Database Persistence**: Stores product catalog and persists every generated bill with itemized product details, subtotal, 5% GST, discounts, and grand totals.
- **Printable Bill Receipt Modal**: Official receipt dialog with unique bill numbers (e.g. `BILL-20260731-1234`), date/time stamp, and print capability.

---

## 📁 Project Structure

```
c:/Project Phase 1/web_app/
│
├── app.py                      # Flask main application & REST API endpoints
├── requirements.txt            # Python dependencies
├── README.md                   # Full documentation & setup guide
│
├── models/
│   └── best.pt                 # YOLOv8 barcode detection model (Place your weights here)
│
├── database/
│   └── supermarket.db          # SQLite database (auto-seeded on first launch)
│
├── services/
│   ├── database_service.py     # SQLite initialization, product search, bill persistence
│   ├── yolo_detector.py        # YOLOv8 model loader (GPU/CPU) & ROI detection
│   └── barcode_decoder.py      # Image preprocessing & Pyzbar/OpenCV barcode decoding
│
├── templates/
│   └── index.html              # Billing dashboard HTML template
│
└── static/
    ├── css/
    │   └── style.css           # Flat yellow-on-white design system
    ├── js/
    │   └── app.js              # Webcam streaming, canvas bounding box, cart management
    └── product_images/         # Product sample thumbnail SVGs
```

---

## 🚀 Quick Setup & Execution Guide

### Prerequisites
- Python 3.9, 3.10, or 3.11 installed
- Webcam / Camera device connected
- *(Optional)* NVIDIA GPU with CUDA for GPU acceleration

### 1. Install Dependencies
Open terminal in the project directory (`c:\Project Phase 1\web_app`):

```bash
pip install -r requirements.txt
```

*(Note for Windows Pyzbar Users: If `pyzbar` reports missing DLLs, install the Visual C++ Redistributable 2013/2015-2022 or rely on the built-in OpenCV BarcodeDetector fallback automatically).*

### 2. Place YOLO Model Weights (Optional)
Copy your trained YOLOv8 PyTorch model `best.pt` into the `models/` directory:
```
models/best.pt
```
*If `best.pt` is not present, BillSightAI will automatically engage its intelligent OpenCV feature extraction mode to scan barcodes without throwing errors.*

### 3. Run the Server
Launch the Flask backend:
```bash
python app.py
```
Output will confirm:
```
* Running on http://127.0.0.1:5000
```

### 4. Access the Web Dashboard
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 📊 Sample Database Barcodes for Testing

| Barcode | Product Name | Category | Price (₹) | Stock |
| :--- | :--- | :--- | :--- | :--- |
| `8901234567890` | Milk | Dairy | ₹30.00 | 100 |
| `8901234567891` | Bread | Bakery | ₹40.00 | 50 |
| `8901234567892` | Biscuits | Snacks | ₹20.00 | 150 |
| `8901234567893` | Apple Juice 1L | Beverages | ₹65.00 | 80 |
| `8901234567894` | Dark Chocolate 100g | Confectionery | ₹85.00 | 120 |
| `8901234567895` | Organic Rice 1kg | Grains | ₹110.00 | 60 |
| `8901234567896` | Bath Soap Pack | Personal Care | ₹45.00 | 200 |
| `8901234567897` | Shampoo 200ml | Personal Care | ₹140.00 | 75 |
| `8901234567898` | Mineral Water 1L | Beverages | ₹20.00 | 300 |
| `8901542001253` | Nycil Powder | Personal Care | ₹155.00 | 100 |
| `8994993016549` | Loreal Foam Cleanser | Personal Care | ₹229.00 | 100 |
| `8901396151005` | Harpic Cleaner | Household Care | ₹110.00 | 100 |

---

## 📡 REST API Documentation

### `GET /api/health`
Checks backend and AI model status.
- **Response**:
  ```json
  {
    "status": "online",
    "model_loaded": true,
    "gpu_available": false,
    "pyzbar_available": true,
    "database_connected": true
  }
  ```

### `POST /api/detect`
Accepts a captured camera frame, runs AI detection & decoding, and returns product data.
- **Input**: `{ "image": "data:image/jpeg;base64,..." }`
- **Success Response**:
  ```json
  {
    "success": true,
    "barcode_detected": true,
    "barcode": "8901234567890",
    "product_found": true,
    "product": {
      "id": 1,
      "barcode": "8901234567890",
      "product_name": "Milk",
      "category": "Dairy",
      "price": 30.0,
      "stock_quantity": 100,
      "image_path": "/static/product_images/milk.svg"
    },
    "confidence": 0.94,
    "bounding_box": { "x1": 120, "y1": 80, "x2": 520, "y2": 300 }
  }
  ```

### `POST /api/bill/generate`
Saves a transaction to the SQLite database and generates a printable invoice.
- **Input**:
  ```json
  {
    "products": [
      { "barcode": "8901234567890", "product_name": "Milk", "price": 30.0, "quantity": 2 }
    ],
    "subtotal": 60.0,
    "gst_percent": 5.0,
    "discount": 0.0
  }
  ```

---

## 🎓 College Demonstration Guide
1. Start `python app.py` and open `http://127.0.0.1:5000`.
2. Click **Start Camera** to activate the webcam.
3. Hold up any product barcode (e.g. Milk `8901234567890` or Bread `8901234567891` barcode image on phone or printed sheet) in front of the lens.
4. Click **Scan Product** or toggle **Auto Scan** for continuous automated scanning.
5. Notice the **Yellow Bounding Box** overlay showing bounding box coordinates, object class, and confidence score.
6. Observe the product immediately added to the **Live Billing Cart**, complete with quantity controls, subtotal, 5% GST, and yellow **Grand Total** block.
7. Click **Generate Bill & Checkout** to open and print the receipt modal.
