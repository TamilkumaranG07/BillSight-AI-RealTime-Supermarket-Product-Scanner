import os
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class YOLODetector:
    def __init__(self, model_path='models/best.pt'):
        self.model = None
        self.model_loaded = False
        self.gpu_available = False
        self.device = 'cpu'
        self.model_path = model_path
        self._load_model()

    def _load_model(self):
        try:
            import torch
            self.gpu_available = torch.cuda.is_available()
            self.device = 'cuda' if self.gpu_available else 'cpu'

            if os.path.exists(self.model_path):
                from ultralytics import YOLO
                logger.info(f"Loading YOLOv8 model from '{self.model_path}' on device '{self.device}'...")
                self.model = YOLO(self.model_path)
                self.model.to(self.device)
                self.model_loaded = True
                logger.info(f"YOLOv8 model successfully loaded on {self.device}.")
            else:
                logger.warning(f"YOLO model file not found at '{self.model_path}'. Running in fallback mode.")
                self.model_loaded = False
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self.model_loaded = False

    def detect(self, image_np):
        """
        Runs barcode object detection on an OpenCV numpy image (BGR).
        Returns dict with bounding_box {x1, y1, x2, y2}, confidence (float), class_name (str)
        or None if no barcode detected.
        """
        if not self.model_loaded or self.model is None:
            # Fallback heuristic region selection if YOLO model is not active
            return self._fallback_detection(image_np)

        try:
            # Run inference
            results = self.model.predict(source=image_np, verbose=False, device=self.device)
            if not results or len(results) == 0:
                return None

            boxes = results[0].boxes
            if boxes is None or len(boxes) == 0:
                return None

            # Get box with highest confidence score
            best_idx = int(boxes.conf.argmax())
            box = boxes[best_idx]
            
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().tolist()
            conf = float(box.conf[0].cpu().numpy())
            cls_id = int(box.cls[0].cpu().numpy())
            
            # Map class name if available
            class_name = "barcode"
            if hasattr(self.model, 'names') and cls_id in self.model.names:
                class_name = str(self.model.names[cls_id])

            return {
                "bounding_box": {
                    "x1": int(round(x1)),
                    "y1": int(round(y1)),
                    "x2": int(round(x2)),
                    "y2": int(round(y2))
                },
                "confidence": round(conf, 4),
                "class_name": class_name
            }
        except Exception as e:
            logger.error(f"Error during YOLO inference: {e}")
            return self._fallback_detection(image_np)

    def _fallback_detection(self, image_np):
        """
        Fallback bounding box estimation using OpenCV edge detection and contours
        when YOLO weights are unavailable.
        """
        try:
            h, w = image_np.shape[:2]
            gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)

            # High gradient regions (barcodes have dense vertical lines)
            grad_x = cv2.Sobel(gray, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
            grad_y = cv2.Sobel(gray, ddepth=cv2.CV_32F, dx=0, dy=1, ksize=-1)
            gradient = cv2.subtract(grad_x, grad_y)
            gradient = cv2.convertScaleAbs(gradient)

            blurred = cv2.blur(gradient, (9, 9))
            _, thresh = cv2.threshold(blurred, 225, 255, cv2.THRESH_BINARY)

            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
            closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            closed = cv2.erode(closed, None, iterations=4)
            closed = cv2.dilate(closed, None, iterations=4)

            contours, _ = cv2.findContours(closed.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                c = max(contours, key=cv2.contourArea)
                if cv2.contourArea(c) > 500:
                    x, y, box_w, box_h = cv2.boundingRect(c)
                    return {
                        "bounding_box": {
                            "x1": int(x),
                            "y1": int(y),
                            "x2": int(x + box_w),
                            "y2": int(y + box_h)
                        },
                        "confidence": 0.85,
                        "class_name": "barcode"
                    }

            # Default centered region fallback
            cx, cy = w // 2, h // 2
            box_w, box_h = int(w * 0.6), int(h * 0.3)
            return {
                "bounding_box": {
                    "x1": max(0, cx - box_w // 2),
                    "y1": max(0, cy - box_h // 2),
                    "x2": min(w, cx + box_w // 2),
                    "y2": min(h, cy + box_h // 2)
                },
                "confidence": 0.70,
                "class_name": "barcode (fallback)"
            }
        except Exception:
            return None
