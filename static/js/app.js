/**
 * BillSightAI – Intelligent Supermarket Billing System
 * Frontend Application Logic (Vanilla JS)
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Element Handles
  const webcamVideo = document.getElementById('webcamVideo');
  const overlayCanvas = document.getElementById('overlayCanvas');
  const canvasCtx = overlayCanvas.getContext('2d');
  const scannerLaser = document.getElementById('scannerLaser');
  const videoPlaceholder = document.getElementById('videoPlaceholder');
  const videoWrapper = document.getElementById('videoWrapper');

  const btnStartCamera = document.getElementById('btnStartCamera');
  const btnStopCamera = document.getElementById('btnStopCamera');
  const btnScanProduct = document.getElementById('btnScanProduct');
  const selectCamera = document.getElementById('selectCamera');
  const toggleAutoScan = document.getElementById('toggleAutoScan');

  const scanBtnSpinner = document.getElementById('scanBtnSpinner');
  const scanBtnIcon = document.getElementById('scanBtnIcon');
  const scanBtnText = document.getElementById('scanBtnText');

  const scannerStatusBox = document.getElementById('scannerStatusBox');
  const statusBoxIcon = document.getElementById('statusBoxIcon');
  const statusBoxText = document.getElementById('statusBoxText');
  const statusBadge = document.getElementById('statusBadge');

  const dotCamera = document.getElementById('dotCamera');
  const labelCamera = document.getElementById('labelCamera');
  const dotAI = document.getElementById('dotAI');
  const labelAI = document.getElementById('labelAI');

  const cartTableBody = document.getElementById('cartTableBody');
  const emptyCartRow = document.getElementById('emptyCartRow');
  const cartItemCount = document.getElementById('cartItemCount');
  const subtotalVal = document.getElementById('subtotalVal');
  const inputGST = document.getElementById('inputGST');
  const gstVal = document.getElementById('gstVal');
  const inputDiscount = document.getElementById('inputDiscount');
  const grandTotalVal = document.getElementById('grandTotalVal');

  const btnClearCart = document.getElementById('btnClearCart');
  const btnGenerateBill = document.getElementById('btnGenerateBill');
  const btnPrintInvoice = document.getElementById('btnPrintInvoice');

  const btnUploadImage = document.getElementById('btnUploadImage');
  const fileUploadInput = document.getElementById('fileUploadInput');

  // Application State
  let mediaStream = null;
  let isCameraActive = false;
  let autoScanInterval = null;
  let isScanningInFlight = false;
  let cart = []; // Array of { product: {...}, quantity: number }

  // Cooldown map: barcode -> timestamp (ms)
  const scannedCooldowns = new Map();
  const COOLDOWN_MS = 3000; // 3 seconds cooldown per barcode

  // --- 1. INITIALIZATION & LIVE CLOCK ---
  initLiveClock();
  checkBackendHealth();
  setupEventListeners();

  function initLiveClock() {
    const clockText = document.getElementById('clockText');
    function updateClock() {
      const now = new Date();
      clockText.textContent = now.toLocaleDateString() + ' ' + now.toLocaleTimeString();
    }
    updateClock();
    setInterval(updateClock, 1000);
  }

  // --- 2. BACKEND HEALTH CHECK ---
  async function checkBackendHealth() {
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      if (data.status === 'online') {
        if (data.model_loaded) {
          dotAI.className = 'status-dot online';
          labelAI.textContent = data.gpu_available ? 'AI Model: GPU (CUDA)' : 'AI Model: CPU (Online)';
        } else {
          dotAI.className = 'status-dot warning';
          labelAI.textContent = 'AI Model: OpenCV Fallback';
        }
      }
    } catch (err) {
      dotAI.className = 'status-dot offline';
      labelAI.textContent = 'AI Model: Offline';
    }
  }

  // --- 3. CAMERA MANAGEMENT ---
  function setupEventListeners() {
    btnStartCamera.addEventListener('click', startCamera);
    btnStopCamera.addEventListener('click', stopCamera);
    btnScanProduct.addEventListener('click', () => captureAndScan(false));
    selectCamera.addEventListener('change', () => {
      if (isCameraActive) {
        startCamera();
      }
    });

    toggleAutoScan.addEventListener('change', (e) => {
      if (e.target.checked) {
        if (!isCameraActive) {
          startCamera().then(() => startAutoScanLoop());
        } else {
          startAutoScanLoop();
        }
      } else {
        stopAutoScanLoop();
      }
    });

    inputGST.addEventListener('input', calculateCartTotals);
    inputDiscount.addEventListener('input', calculateCartTotals);

    btnClearCart.addEventListener('click', clearCart);
    btnGenerateBill.addEventListener('click', generateBillAndShowModal);
    btnPrintInvoice.addEventListener('click', generateBillAndShowModal);

    if (btnUploadImage && fileUploadInput) {
      btnUploadImage.addEventListener('click', () => fileUploadInput.click());
      fileUploadInput.addEventListener('change', handleFileUploadScan);
    }
  }

  async function handleFileUploadScan(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async function(event) {
      const base64Image = event.target.result;
      const img = new Image();
      img.onload = async function() {
        overlayCanvas.width = img.width;
        overlayCanvas.height = img.height;

        videoPlaceholder.style.display = 'none';
        canvasCtx.drawImage(img, 0, 0, overlayCanvas.width, overlayCanvas.height);

        setScanBtnLoading(true);
        updateStatusBox('Analyzing uploaded image file...', 'PROCESSING', 'badge-warning');

        try {
          const res = await fetch('/api/detect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: base64Image })
          });
          const data = await res.json();

          // Redraw image onto canvas before drawing bounding box overlay
          canvasCtx.drawImage(img, 0, 0, overlayCanvas.width, overlayCanvas.height);
          processDetectionResult(data, false);
        } catch (err) {
          console.error('File scan error:', err);
          updateStatusBox('Failed to scan uploaded image file.', 'ERROR', 'badge-error');
        } finally {
          setScanBtnLoading(false);
          fileUploadInput.value = '';
        }
      };
      img.src = base64Image;
    };
    reader.readAsDataURL(file);
  }

  async function populateCameraDevices() {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = devices.filter(d => d.kind === 'videoinput');
      selectCamera.innerHTML = '';

      if (videoDevices.length === 0) {
        selectCamera.innerHTML = '<option value="">No camera device found</option>';
        selectCamera.disabled = true;
        return;
      }

      videoDevices.forEach((device, idx) => {
        const option = document.createElement('option');
        option.value = device.deviceId;
        option.textContent = device.label || `Camera ${idx + 1} (${device.deviceId.substring(0, 8)}...)`;
        selectCamera.appendChild(option);
      });
      selectCamera.disabled = false;
    } catch (err) {
      console.warn('Could not enumerate media devices:', err);
    }
  }

  async function startCamera() {
    try {
      const selectedDeviceId = selectCamera.value;
      const constraints = {
        video: selectedDeviceId ? { deviceId: { exact: selectedDeviceId } } : { facingMode: 'environment' }
      };

      if (mediaStream) {
        stopCameraTracks();
      }

      mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
      webcamVideo.srcObject = mediaStream;

      webcamVideo.onloadedmetadata = () => {
        webcamVideo.play();
        resizeOverlayCanvas();
        videoPlaceholder.style.display = 'none';
        scannerLaser.style.display = 'block';

        isCameraActive = true;
        btnStartCamera.disabled = true;
        btnStopCamera.disabled = false;
        btnScanProduct.disabled = false;

        dotCamera.className = 'status-dot online';
        labelCamera.textContent = 'Camera: Active';

        updateStatusBox('Camera stream active. Ready for barcode scanning.', 'IDLE', 'badge-warning');
        populateCameraDevices();
      };
    } catch (err) {
      console.error('Camera Access Error:', err);
      dotCamera.className = 'status-dot offline';
      labelCamera.textContent = 'Camera: Denied/Error';
      updateStatusBox('Failed to access camera feed: ' + err.message, 'ERROR', 'badge-error');
      alert('Camera Permission Denied or Device Unavailable. Please allow camera permissions in browser settings.');
    }
  }

  function stopCamera() {
    stopAutoScanLoop();
    toggleAutoScan.checked = false;
    stopCameraTracks();

    webcamVideo.srcObject = null;
    videoPlaceholder.style.display = 'block';
    scannerLaser.style.display = 'none';
    clearOverlayCanvas();

    isCameraActive = false;
    btnStartCamera.disabled = false;
    btnStopCamera.disabled = true;
    btnScanProduct.disabled = true;

    dotCamera.className = 'status-dot offline';
    labelCamera.textContent = 'Camera: Offline';

    updateStatusBox('Camera stream stopped.', 'OFFLINE', 'badge-error');
  }

  function stopCameraTracks() {
    if (mediaStream) {
      mediaStream.getTracks().forEach(track => track.stop());
      mediaStream = null;
    }
  }

  function resizeOverlayCanvas() {
    if (webcamVideo.videoWidth && webcamVideo.videoHeight) {
      overlayCanvas.width = webcamVideo.videoWidth;
      overlayCanvas.height = webcamVideo.videoHeight;
    }
  }

  // --- 4. AUTO SCAN LOOP & COOLDOWN MANAGEMENT ---
  function startAutoScanLoop() {
    if (autoScanInterval) clearInterval(autoScanInterval);
    autoScanInterval = setInterval(() => {
      if (isCameraActive && !isScanningInFlight) {
        captureAndScan(true);
      }
    }, 1500);
  }

  function stopAutoScanLoop() {
    if (autoScanInterval) {
      clearInterval(autoScanInterval);
      autoScanInterval = null;
    }
  }

  // --- 5. CAPTURE & AI SCANNING PIPELINE ---
  async function captureAndScan(isAutoScan = false) {
    if (!isCameraActive || isScanningInFlight) return;

    try {
      isScanningInFlight = true;
      if (!isAutoScan) {
        setScanBtnLoading(true);
      }

      resizeOverlayCanvas();
      const tempCanvas = document.createElement('canvas');
      tempCanvas.width = webcamVideo.videoWidth || 640;
      tempCanvas.height = webcamVideo.videoHeight || 480;
      const ctx = tempCanvas.getContext('2d');
      ctx.drawImage(webcamVideo, 0, 0, tempCanvas.width, tempCanvas.height);

      const base64Image = tempCanvas.toDataURL('image/jpeg', 0.85);

      // Call Backend AI Endpoint
      const res = await fetch('/api/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: base64Image })
      });

      const data = await res.json();
      processDetectionResult(data, isAutoScan);

    } catch (err) {
      console.error('Scan Request Error:', err);
      updateStatusBox('Server connection error during scan.', 'ERROR', 'badge-error');
    } finally {
      isScanningInFlight = false;
      if (!isAutoScan) {
        setScanBtnLoading(false);
      }
    }
  }

  function processDetectionResult(data, isAutoScan) {
    clearOverlayCanvas();

    if (data.success && data.barcode_detected && data.product_found) {
      const barcode = data.barcode;
      const now = Date.now();

      // Check Cooldown for continuous auto-scan
      if (isAutoScan && scannedCooldowns.has(barcode)) {
        const lastScanTime = scannedCooldowns.get(barcode);
        if (now - lastScanTime < COOLDOWN_MS) {
          // Inside cooldown window - draw bounding box without re-adding to cart
          drawBoundingBox(data.bounding_box, data.product.product_name, data.confidence);
          updateStatusBox(`Barcode '${barcode}' detected (Cooldown active)`, 'COOLDOWN', 'badge-warning');
          return;
        }
      }

      // Add to Cooldown map
      scannedCooldowns.set(barcode, now);

      // Draw bounding box on canvas overlay
      drawBoundingBox(data.bounding_box, `${data.product.product_name} (${(data.confidence * 100).toFixed(0)}%)`, data.confidence);

      // Add to Cart
      addProductToCart(data.product);

      updateStatusBox(`Scanned: ${data.product.product_name} - ₹${data.product.price.toFixed(2)}`, 'DETECTED', 'badge-success');

    } else if (data.barcode_detected && !data.product_found) {
      if (data.bounding_box) {
        drawBoundingBox(data.bounding_box, `Unknown: ${data.barcode}`, data.confidence);
      }
      updateStatusBox(`Barcode '${data.barcode}' detected, but product is not in database.`, 'NOT FOUND', 'badge-warning');

    } else {
      updateStatusBox(data.message || 'No barcode detected. Position product clearly.', 'NO DETECTION', 'badge-error');
    }
  }

  function drawBoundingBox(bbox, label, confidence) {
    if (!bbox) return;

    const { x1, y1, x2, y2 } = bbox;
    const width = x2 - x1;
    const height = y2 - y1;

    // Outer Yellow Bounding Box (Flat #FFC107)
    canvasCtx.strokeStyle = '#FFC107';
    canvasCtx.lineWidth = 4;
    canvasCtx.strokeRect(x1, y1, width, height);

    // Label Header Tag
    const tagText = `${label}`;
    canvasCtx.font = 'bold 16px Inter, sans-serif';
    const textWidth = canvasCtx.measureText(tagText).width;

    canvasCtx.fillStyle = '#FFC107';
    canvasCtx.fillRect(x1, Math.max(0, y1 - 26), textWidth + 16, 26);

    canvasCtx.fillStyle = '#1A1A1A';
    canvasCtx.fillText(tagText, x1 + 8, Math.max(18, y1 - 8));
  }

  function clearOverlayCanvas() {
    canvasCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
  }

  function updateStatusBox(message, statusText, badgeClass) {
    statusBoxText.textContent = message;
    statusBadge.textContent = statusText;
    statusBadge.className = `detection-badge ${badgeClass}`;
  }

  function setScanBtnLoading(isLoading) {
    if (isLoading) {
      scanBtnSpinner.classList.remove('d-none');
      scanBtnIcon.classList.add('d-none');
      scanBtnText.textContent = 'Processing AI Inference...';
      btnScanProduct.disabled = true;
    } else {
      scanBtnSpinner.classList.add('d-none');
      scanBtnIcon.classList.remove('d-none');
      scanBtnText.textContent = 'Scan Product (Capture Frame)';
      btnScanProduct.disabled = !isCameraActive;
    }
  }

  // --- 6. CART & BILLING LOGIC ---
  function addProductToCart(product) {
    const existingIndex = cart.findIndex(item => item.product.barcode === product.barcode);
    if (existingIndex > -1) {
      cart[existingIndex].quantity += 1;
    } else {
      cart.push({ product, quantity: 1 });
    }
    renderCartTable();
  }

  function renderCartTable() {
    cartTableBody.innerHTML = '';

    if (cart.length === 0) {
      cartTableBody.appendChild(emptyCartRow);
      btnGenerateBill.disabled = true;
      btnPrintInvoice.disabled = true;
      calculateCartTotals();
      return;
    }

    btnGenerateBill.disabled = false;
    btnPrintInvoice.disabled = false;

    cart.forEach((item, index) => {
      const p = item.product;
      const itemTotal = p.price * item.quantity;

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="fw-bold">${index + 1}</td>
        <td>
          <div class="d-flex align-items-center gap-2">
            <img src="${p.image_path || '/static/product_images/milk.svg'}" class="product-thumb" alt="${p.product_name}" onerror="this.src='/static/product_images/milk.svg'">
            <div>
              <div class="fw-bold text-dark">${escapeHtml(p.product_name)}</div>
              <small class="text-muted">${escapeHtml(p.category)}</small>
            </div>
          </div>
        </td>
        <td><code class="text-dark bg-light px-2 py-1 rounded">${escapeHtml(p.barcode)}</code></td>
        <td class="fw-bold">₹${p.price.toFixed(2)}</td>
        <td style="text-align: center;">
          <div class="qty-control">
            <button class="qty-btn" onclick="updateQty(${index}, -1)">-</button>
            <span class="qty-val">${item.quantity}</span>
            <button class="qty-btn" onclick="updateQty(${index}, 1)">+</button>
          </div>
        </td>
        <td style="text-align: right;" class="fw-bold text-dark">₹${itemTotal.toFixed(2)}</td>
        <td>
          <button class="btn btn-sm btn-flat-danger p-1 text-center" onclick="removeCartRow(${index})" title="Remove item">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </td>
      `;
      cartTableBody.appendChild(tr);
    });

    calculateCartTotals();
  }

  window.updateQty = function(index, delta) {
    if (cart[index]) {
      cart[index].quantity += delta;
      if (cart[index].quantity <= 0) {
        cart.splice(index, 1);
      }
      renderCartTable();
    }
  };

  window.removeCartRow = function(index) {
    if (cart[index]) {
      cart.splice(index, 1);
      renderCartTable();
    }
  };

  function clearCart() {
    if (cart.length === 0) return;
    if (confirm('Are you sure you want to clear the billing cart?')) {
      cart = [];
      renderCartTable();
    }
  }

  function calculateCartTotals() {
    const totalItems = cart.reduce((acc, item) => acc + item.quantity, 0);
    const subtotal = cart.reduce((acc, item) => acc + (item.product.price * item.quantity), 0);

    const gstRate = parseFloat(inputGST.value) || 0;
    const discount = parseFloat(inputDiscount.value) || 0;

    const gstAmount = subtotal * (gstRate / 100);
    const grandTotal = Math.max(0, subtotal + gstAmount - discount);

    cartItemCount.textContent = totalItems;
    subtotalVal.textContent = subtotal.toFixed(2);
    gstVal.textContent = gstAmount.toFixed(2);
    grandTotalVal.textContent = grandTotal.toFixed(2);
  }

  // --- 7. GENERATE BILL, QR PAYMENT & INVOICE PREVIEW ---
  let currentBillData = null;

  async function generateBillAndShowModal() {
    if (cart.length === 0) {
      alert('Cart is empty. Scan products before generating a bill.');
      return;
    }

    const subtotal = cart.reduce((acc, item) => acc + (item.product.price * item.quantity), 0);
    const gstRate = parseFloat(inputGST.value) || 5.0;
    const discount = parseFloat(inputDiscount.value) || 0.0;

    const payloadProducts = cart.map(item => ({
      barcode: item.product.barcode,
      product_name: item.product.product_name,
      category: item.product.category,
      price: item.product.price,
      quantity: item.quantity,
      total: item.product.price * item.quantity
    }));

    try {
      const res = await fetch('/api/bill/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          products: payloadProducts,
          subtotal: subtotal,
          gst_percent: gstRate,
          discount: discount
        })
      });

      const data = await res.json();
      if (data.success && data.bill) {
        currentBillData = data.bill;
        populateReceiptModal(data.bill, data.qr_image_url);
        const receiptModal = new bootstrap.Modal(document.getElementById('receiptModal'));
        receiptModal.show();
      } else {
        alert('Failed to generate bill: ' + (data.message || 'Unknown error'));
      }
    } catch (err) {
      console.error('Bill Generation Error:', err);
      alert('Error connecting to backend for bill generation.');
    }
  }

  function populateReceiptModal(bill, qrImageUrl) {
    document.getElementById('modalBillNo').textContent = bill.bill_number;
    document.getElementById('modalBillDate').textContent = bill.timestamp;
    document.getElementById('modalSubtotal').textContent = bill.subtotal.toFixed(2);
    document.getElementById('modalGstRate').textContent = bill.gst_percent;
    document.getElementById('modalGstAmount').textContent = bill.gst_amount.toFixed(2);
    document.getElementById('modalDiscount').textContent = bill.discount.toFixed(2);
    document.getElementById('modalGrandTotal').textContent = bill.grand_total.toFixed(2);
    document.getElementById('modalQrAmount').textContent = bill.grand_total.toFixed(2);

    // QR Code Image Setup
    const qrImg = document.getElementById('modalQrCodeImg');
    const fallbackQr = `https://quickchart.io/qr?text=upi%3A%2F%2Fpay%3Fpa%3Dbillsight%40upi%26am%3D${bill.grand_total.toFixed(2)}&size=200`;
    qrImg.src = qrImageUrl || fallbackQr;

    // Reset Payment Badge & Trigger Button State
    const badge = document.getElementById('modalPaymentBadge');
    const btnPay = document.getElementById('btnSimulateQrPay');
    const notice = document.getElementById('paymentSuccessNotice');

    if (notice) notice.classList.add('d-none');

    if (bill.payment_status === 'Completed' || bill.payment_status === 'PAID') {
      badge.className = 'badge bg-success text-white fs-7 px-3 py-1';
      badge.innerHTML = `<i class="fa-solid fa-circle-check me-1"></i> PAID & CONFIRMED`;
      if (btnPay) {
        btnPay.className = 'btn btn-sm btn-outline-success disabled fw-bold px-3 py-2';
        btnPay.innerHTML = `<i class="fa-solid fa-check me-1"></i> Payment Verified`;
        btnPay.disabled = true;
      }
    } else {
      badge.className = 'badge bg-warning text-dark fs-7 px-3 py-1';
      badge.innerHTML = `<i class="fa-solid fa-clock me-1"></i> PENDING PAYMENT`;
      if (btnPay) {
        btnPay.className = 'btn btn-sm btn-success fw-bold px-3 py-2';
        btnPay.innerHTML = `<i class="fa-solid fa-mobile-screen-button me-1"></i> Scan / Trigger QR Payment`;
        btnPay.disabled = false;
      }
    }

    const itemsTbody = document.getElementById('modalReceiptItems');
    itemsTbody.innerHTML = '';

    bill.products.forEach(item => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${escapeHtml(item.product_name)}</td>
        <td style="text-align: center;">${item.quantity}</td>
        <td style="text-align: right;">₹${item.price.toFixed(2)}</td>
        <td style="text-align: right;" class="fw-bold">₹${(item.price * item.quantity).toFixed(2)}</td>
      `;
      itemsTbody.appendChild(tr);
    });

    // Prepare Invoice Preview Image
    generateAndShowInvoiceImage(bill);
  }

  // QR PAYMENT SIMULATION / SCAN TRIGGER HANDLER
  const btnSimulateQrPay = document.getElementById('btnSimulateQrPay');
  if (btnSimulateQrPay) {
    btnSimulateQrPay.addEventListener('click', async () => {
      if (!currentBillData || !currentBillData.bill_number) return;

      btnSimulateQrPay.disabled = true;
      btnSimulateQrPay.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span> Processing...`;

      try {
        const res = await fetch(`/api/bill/${currentBillData.bill_number}/pay`, { method: 'POST' });
        const data = await res.json();

        if (data.success) {
          currentBillData.payment_status = 'Completed';
          const badge = document.getElementById('modalPaymentBadge');
          if (badge) {
            badge.className = 'badge bg-success text-white fs-7 px-3 py-1';
            badge.innerHTML = `<i class="fa-solid fa-circle-check me-1"></i> PAID & CONFIRMED`;
          }

          const notice = document.getElementById('paymentSuccessNotice');
          if (notice) {
            notice.classList.remove('d-none');
            document.getElementById('paidAmountNotice').textContent = currentBillData.grand_total.toFixed(2);
          }

          btnSimulateQrPay.className = 'btn btn-sm btn-outline-success disabled fw-bold px-3 py-2';
          btnSimulateQrPay.innerHTML = `<i class="fa-solid fa-check me-1"></i> Payment Verified`;

          // Refresh Invoice Image preview
          generateAndShowInvoiceImage(currentBillData);
        } else {
          alert('Payment trigger failed: ' + (data.message || 'Unknown error'));
          btnSimulateQrPay.disabled = false;
          btnSimulateQrPay.innerHTML = `<i class="fa-solid fa-mobile-screen-button me-1"></i> Scan / Trigger QR Payment`;
        }
      } catch (err) {
        console.error('Payment Trigger Error:', err);
        alert('Network error during QR payment confirmation.');
        btnSimulateQrPay.disabled = false;
        btnSimulateQrPay.innerHTML = `<i class="fa-solid fa-mobile-screen-button me-1"></i> Scan / Trigger QR Payment`;
      }
    });
  }

  // PRINT & INVOICE IMAGE PREVIEW BUTTONS HANDLERS
  const btnPreviewInvoiceImage = document.getElementById('btnPreviewInvoiceImage');
  if (btnPreviewInvoiceImage) {
    btnPreviewInvoiceImage.addEventListener('click', () => {
      if (currentBillData) {
        generateAndShowInvoiceImage(currentBillData);
        const imageModal = new bootstrap.Modal(document.getElementById('invoiceImageModal'));
        imageModal.show();
      }
    });
  }

  const btnPrintReceiptDirect = document.getElementById('btnPrintReceiptDirect');
  if (btnPrintReceiptDirect) {
    btnPrintReceiptDirect.addEventListener('click', () => {
      window.print();
    });
  }

  const btnPrintFromImageModal = document.getElementById('btnPrintFromImageModal');
  if (btnPrintFromImageModal) {
    btnPrintFromImageModal.addEventListener('click', () => {
      window.print();
    });
  }

  // GENERATE THERMAL INVOICE RECEIPT CANVAS IMAGE
  function generateAndShowInvoiceImage(bill) {
    if (!bill) return;

    const canvas = document.createElement('canvas');
    canvas.width = 440;
    const items = bill.products || [];
    const baseHeight = 490 + items.length * 28;
    canvas.height = baseHeight;

    const ctx = canvas.getContext('2d');

    // Background
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Yellow Brand Header
    ctx.fillStyle = '#FFC107';
    ctx.fillRect(0, 0, canvas.width, 90);

    ctx.fillStyle = '#1A1A1A';
    ctx.font = 'bold 22px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('BillSightAI Supermarket', canvas.width / 2, 40);

    ctx.font = '12px Inter, sans-serif';
    ctx.fillText('123 College Campus Road, Innovation Tech Park', canvas.width / 2, 60);
    ctx.fillText('GSTIN: 33AAAAA0000A1Z5 | Phone: +91 98765 43210', canvas.width / 2, 76);

    // Bill Metadata
    ctx.fillStyle = '#1A1A1A';
    ctx.font = '12px Inter, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(`Bill No: ${bill.bill_number}`, 20, 120);
    ctx.fillText(`Date: ${bill.timestamp}`, 20, 138);

    const isPaid = (bill.payment_status === 'Completed' || bill.payment_status === 'PAID');
    ctx.textAlign = 'right';
    ctx.fillStyle = isPaid ? '#2E7D32' : '#F57C00';
    ctx.font = 'bold 13px Inter, sans-serif';
    ctx.fillText(isPaid ? 'STATUS: PAID' : 'STATUS: PENDING PAYMENT', canvas.width - 20, 120);

    // Separator
    ctx.strokeStyle = '#CCCCCC';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(20, 155);
    ctx.lineTo(canvas.width - 20, 155);
    ctx.stroke();

    // Table Headers
    ctx.fillStyle = '#1A1A1A';
    ctx.font = 'bold 12px Inter, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('Item', 20, 175);
    ctx.textAlign = 'center';
    ctx.fillText('Qty', 240, 175);
    ctx.textAlign = 'right';
    ctx.fillText('Price', 330, 175);
    ctx.fillText('Total', canvas.width - 20, 175);

    ctx.beginPath();
    ctx.moveTo(20, 185);
    ctx.lineTo(canvas.width - 20, 185);
    ctx.stroke();

    // Item Rows
    let y = 210;
    ctx.font = '12px Inter, sans-serif';
    items.forEach(item => {
      ctx.textAlign = 'left';
      ctx.fillStyle = '#1A1A1A';
      const name = item.product_name.length > 20 ? item.product_name.substring(0, 18) + '..' : item.product_name;
      ctx.fillText(name, 20, y);

      ctx.textAlign = 'center';
      ctx.fillText(item.quantity.toString(), 240, y);

      ctx.textAlign = 'right';
      ctx.fillText(`₹${item.price.toFixed(2)}`, 330, y);
      ctx.fillText(`₹${(item.price * item.quantity).toFixed(2)}`, canvas.width - 20, y);
      y += 26;
    });

    ctx.beginPath();
    ctx.moveTo(20, y);
    ctx.lineTo(canvas.width - 20, y);
    ctx.stroke();
    y += 20;

    // Totals Breakdown
    ctx.textAlign = 'left';
    ctx.fillStyle = '#6B6B6B';
    ctx.fillText('Subtotal:', 20, y);
    ctx.textAlign = 'right';
    ctx.fillText(`₹${bill.subtotal.toFixed(2)}`, canvas.width - 20, y);
    y += 20;

    ctx.textAlign = 'left';
    ctx.fillText(`GST (${bill.gst_percent}%):`, 20, y);
    ctx.textAlign = 'right';
    ctx.fillText(`+ ₹${bill.gst_amount.toFixed(2)}`, canvas.width - 20, y);
    y += 20;

    if (bill.discount > 0) {
      ctx.textAlign = 'left';
      ctx.fillStyle = '#C62828';
      ctx.fillText('Discount:', 20, y);
      ctx.textAlign = 'right';
      ctx.fillText(`- ₹${bill.discount.toFixed(2)}`, canvas.width - 20, y);
      y += 20;
    }

    // Grand Total Highlight
    y += 10;
    ctx.fillStyle = '#FFC107';
    ctx.fillRect(20, y, canvas.width - 40, 45);

    ctx.fillStyle = '#1A1A1A';
    ctx.font = 'bold 15px Inter, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('GRAND TOTAL:', 35, y + 28);

    ctx.font = 'bold 18px Inter, sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(`₹${bill.grand_total.toFixed(2)}`, canvas.width - 35, y + 28);
    y += 65;

    // Footer & Barcode
    ctx.textAlign = 'center';
    ctx.fillStyle = '#6B6B6B';
    ctx.font = '12px Inter, sans-serif';
    ctx.fillText('Thank You for Shopping with BillSightAI!', canvas.width / 2, y);
    y += 25;

    ctx.fillStyle = '#1A1A1A';
    ctx.font = '18px monospace';
    ctx.fillText('||||| ||| ||||||| |||| ||', canvas.width / 2, y);

    const imgDataUrl = canvas.toDataURL('image/png');
    const previewImg = document.getElementById('invoicePreviewImg');
    if (previewImg) {
      previewImg.src = imgDataUrl;
    }
  }

  // --- 8. REAL-TIME BACKEND PRODUCT & DISCOUNT POLLING ---
  async function pollProductsFromBackend() {
    try {
      const res = await fetch('/api/products');
      if (!res.ok) return;
      const products = await res.json();
      if (!Array.isArray(products)) return;

      let hasChanged = false;
      products.forEach(latestP => {
        const cartItem = cart.find(item => item.product.barcode === latestP.barcode || item.product.id === latestP.id);
        if (cartItem) {
          const discountPct = parseFloat(latestP.discountPercent || 0);
          const basePrice = parseFloat(latestP.price || 0);
          const effectivePrice = discountPct > 0 
            ? Math.round(basePrice * (1 - discountPct / 100) * 100) / 100 
            : basePrice;
          
          if (cartItem.product.price !== effectivePrice || cartItem.product.discountPercent !== discountPct) {
            cartItem.product.price = effectivePrice;
            cartItem.product.discountPercent = discountPct;
            hasChanged = true;
          }
        }
      });

      if (hasChanged) {
        renderCartTable();
      }
    } catch (e) {
      // Ignore network polling glitches quietly
    }
  }
  setInterval(pollProductsFromBackend, 2500);

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
  }
});

