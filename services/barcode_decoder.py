import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Check if pyzbar is available
PYZBAR_AVAILABLE = False
try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except Exception as e:
    logger.warning(f"pyzbar library not available or zbar DLL missing: {e}. Falling back to OpenCV BarcodeDetector.")

class BarcodeDecoder:
    def decode(self, image_np, bbox=None):
        """
        Crop barcode region if bbox is provided, preprocess crop, and attempt pyzbar / OpenCV decode.
        Returns decoded barcode string or None.
        """
        if image_np is None or image_np.size == 0:
            return None

        h, w = image_np.shape[:2]

        crops_to_try = []

        # 1. Bounding box crop with padding
        if bbox:
            x1 = max(0, int(bbox.get('x1', 0)) - 15)
            y1 = max(0, int(bbox.get('y1', 0)) - 15)
            x2 = min(w, int(bbox.get('x2', w)) + 15)
            y2 = min(h, int(bbox.get('y2', h)) + 15)
            if (x2 - x1) > 10 and (y2 - y1) > 10:
                roi = image_np[y1:y2, x1:x2]
                crops_to_try.append(roi)

        # 2. Full image as backup candidate
        crops_to_try.append(image_np)

        # Iterate over candidate crops
        for crop in crops_to_try:
            # Generate preprocessed variations
            preprocessed_images = self._preprocess_variations(crop)

            for img_var in preprocessed_images:
                # Attempt decoding with Pyzbar
                code = self._decode_pyzbar(img_var)
                if code:
                    return code

                # Attempt decoding with OpenCV Barcode Detector
                code = self._decode_opencv(img_var)
                if code:
                    return code

        return None

    def _preprocess_variations(self, image_np):
        """
        Creates multiple preprocessed variations of an image (grayscale, contrast-enhanced, thresholded, sharpened)
        to maximize barcode reading rate.
        """
        variations = []
        if len(image_np.shape) == 3:
            gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)
        else:
            gray = image_np.copy()

        # Original grayscale
        variations.append(gray)

        # Resize if crop is too small
        gh, gw = gray.shape[:2]
        if gh < 150 or gw < 150:
            scale = max(2.0, 300.0 / max(gh, gw))
            gray_resized = cv2.resize(gray, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            variations.append(gray_resized)

        # CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        contrast_enhanced = clahe.apply(gray)
        variations.append(contrast_enhanced)

        # Otsu thresholding
        _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        variations.append(otsu)

        # Sharpening kernel
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        sharpened = cv2.filter2D(gray, -1, kernel)
        variations.append(sharpened)

        return variations

    def _decode_pyzbar(self, image_gray):
        if not PYZBAR_AVAILABLE:
            return None
        try:
            barcodes = pyzbar.decode(image_gray)
            for barcode in barcodes:
                barcode_data = barcode.data.decode("utf-8").strip()
                if barcode_data:
                    return barcode_data
        except Exception as e:
            logger.debug(f"Pyzbar decoding error: {e}")
        return None

    def _decode_opencv(self, image_gray):
        try:
            # OpenCV BarcodeDetector (available in opencv-python >= 4.5.3)
            if hasattr(cv2, 'barcode') and hasattr(cv2.barcode, 'BarcodeDetector'):
                detector = cv2.barcode.BarcodeDetector()
                ok, decoded_info, _, _ = detector.detectAndDecode(image_gray)
                if ok and decoded_info:
                    for info in decoded_info:
                        if info and info.strip():
                            return info.strip()
            
            # Alternative: QRCodeDetector fallback
            qr_detector = cv2.QRCodeDetector()
            info, _, _ = qr_detector.detectAndDecode(image_gray)
            if info and info.strip():
                return info.strip()
        except Exception as e:
            logger.debug(f"OpenCV barcode decoder error: {e}")
        return None
