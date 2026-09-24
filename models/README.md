# BillSightAI - Model Weights Directory

Place your custom-trained YOLOv8 PyTorch model file here named `best.pt`.

Path: `models/best.pt`

When `best.pt` is present in this folder, the Flask backend will automatically load it on startup, detect CUDA GPU availability, and utilize YOLOv8 for precise barcode region detection.

If `best.pt` is missing, the backend will automatically fallback to OpenCV intelligent ROI feature extraction and barcode scanning.
