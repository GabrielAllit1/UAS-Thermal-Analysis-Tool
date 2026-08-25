import sys
import os
# Set GDAL_DATA environment variable to suppress warning
os.environ['GDAL_DATA'] = "C:\\Users\\GAllit\\AppData\\Local\\anaconda3\\envs\\thermal_analysis_64_new\\Library\\share\\gdal"
# Disable MKL features that require MPI, PGI, or GPU support
os.environ['MKL_DISABLE_FAST_MM'] = '1'
os.environ['MKL_THREADING_LAYER'] = 'sequential'
os.environ['MKL_ENABLE_INSTRUCTIONS'] = 'SSE4_2'  # Use a minimal instruction set
os.environ['MKL_NUM_THREADS'] = '1'  # Disable multi-threading
os.environ['MKL_DYNAMIC'] = 'FALSE'  # Disable dynamic loading of MKL libraries
import datetime
import json
import base64
import hmac
import hashlib
# Import minimal PyQt5 modules needed for license check
from PyQt5.QtWidgets import QApplication, QMessageBox, QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel
from PyQt5.QtCore import QCoreApplication, QUrl
from PyQt5.QtGui import QDesktopServices

# Set matplotlib backend to avoid Qt conflicts during import
os.environ['MPLBACKEND'] = 'Agg'  # Use non-interactive backend to prevent Qt interaction

# Load the secret key from a file bundled with the executable
def load_secret_key():
    if hasattr(sys, '_MEIPASS'):
        key_path = os.path.join(sys._MEIPASS, "secure_key.dat")
    else:
        key_path = os.path.join(os.path.dirname(__file__), "secure_key.dat")
    print(f"Attempting to load secret key from: {key_path}")  # Debug print
    if not os.path.exists(key_path):
        raise FileNotFoundError("secure_key.dat not found. Please ensure the secret key file is included.")
    with open(key_path, "rb") as key_file:
        return key_file.read()

SECRET_KEY = load_secret_key()

SUPPORT_EMAIL = "salt19.llc@gmail.com"

def validate_license_key(license_key):
    """
    Validate a license key and return the license data.
    
    Args:
        license_key (str): License key in the format base64_data.signature.
    
    Returns:
        tuple: (bool, dict/str) - (is_valid, license_data or error message)
    """
    try:
        # Split the key into data and signature
        license_b64, signature = license_key.split('.')
        # Verify the signature
        expected_signature = hmac.new(SECRET_KEY, license_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return False, "Invalid license key: Signature verification failed."
        # Decode the Base64 data
        license_json = base64.urlsafe_b64decode(license_b64).decode()
        license_data = json.loads(license_json)
        return True, license_data
    except Exception as e:
        return False, f"Invalid license key: {str(e)}"

def save_license_data(license_data):
    """Save the license data to a local file."""
    with open("license_data.dat", "w") as f:
        json.dump(license_data, f)

def load_license_data():
    """Load the license data from the local file."""
    if not os.path.exists("license_data.dat"):
        return None
    try:
        with open("license_data.dat", "r") as f:
            return json.load(f)
    except:
        return None

def update_last_checked():
    """Update the last checked timestamp to detect clock tampering."""
    with open("last_check.dat", "w") as f:
        f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

def check_clock_tampering():
    """Check for system clock tampering."""
    if not os.path.exists("last_check.dat"):
        update_last_checked()
        return True, "First run."
    
    with open("last_check.dat", "r") as f:
        last_checked = datetime.datetime.strptime(f.read(), "%Y-%m-%d %H:%M:%S")
    
    current_time = datetime.datetime.now()
    if current_time < last_checked:
        return False, "System clock tampering detected. Please set the correct date and time."
    
    update_last_checked()
    return True, "Clock is valid."

def check_license(app):
    """Check if the current license is valid, or prompt for a new license key."""
    # First, check for clock tampering
    clock_valid, clock_message = check_clock_tampering()
    if not clock_valid:
        return False, clock_message
    
    license_data = load_license_data()
    current_date = datetime.datetime.now()
    
    if license_data:
        expiration_date = datetime.datetime.strptime(license_data["expiration_date"], "%Y-%m-%d")
        if current_date <= expiration_date:
            # License is valid
            warning_period = datetime.timedelta(days=30)
            if expiration_date - current_date <= warning_period:
                remaining_days = (expiration_date - current_date).days
                QMessageBox.warning(None, "License Warning", f"Your license will expire in {remaining_days} days on {license_data['expiration_date']}.\nContact support at {SUPPORT_EMAIL} to renew.")
            return True, "License is valid."
    
    # License is missing or expired; prompt for a new key
    dialog = QDialog()
    dialog.setWindowTitle("License Key Required")
    layout = QVBoxLayout()
    
    message = f"Please enter your license key to activate or renew your license.\nContact support at {SUPPORT_EMAIL} to obtain a key."
    if license_data:
        message = f"License expired on {license_data['expiration_date']}.\nPlease enter a new license key to renew.\nContact support at {SUPPORT_EMAIL} to obtain a key."
    layout.addWidget(QLabel(message))
    
    key_input = QLineEdit()
    key_input.setPlaceholderText("Enter license key")
    layout.addWidget(key_input)
    
    # Add a button to open the support email in the default email client
    contact_button = QPushButton("Contact Support")
    contact_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(f"mailto:{SUPPORT_EMAIL}?subject=License Renewal Request")))
    layout.addWidget(contact_button)
    
    submit_button = QPushButton("Submit")
    layout.addWidget(submit_button)
    
    def on_submit():
        key = key_input.text().strip()
        if not key:
            QMessageBox.warning(dialog, "Error", "Please enter a license key.")
            return
        
        is_valid, result = validate_license_key(key)
        if not is_valid:
            QMessageBox.critical(dialog, "Error", result)
            return
        
        # License key is valid; save the new license data
        save_license_data(result)
        QMessageBox.information(dialog, "Success", "License activated successfully. The application will now restart.")
        dialog.accept()
        # Restart the app
        QCoreApplication.quit()
        os.execv(sys.executable, [sys.executable] + sys.argv)
    
    submit_button.clicked.connect(on_submit)
    dialog.setLayout(layout)
    dialog.exec_()
    return False, "License key required."

# Check license before starting the app
if __name__ == "__main__":
    # Create QApplication first
    print("Initializing QApplication...")
    app = QApplication(sys.argv)
    print("QApplication initialized.")

    # Check license
    print("Checking license...")
    is_valid, message = check_license(app)
    if not is_valid:
        print("License check failed:", message)
        QMessageBox.critical(None, "License Error", message)
        sys.exit(1)
    
    # Import remaining modules only after license check passes
    print("Importing remaining modules...")
    from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QTextEdit, QProgressBar, QComboBox, QFormLayout
    from PyQt5.QtGui import QPixmap, QImage
    from PyQt5.QtCore import Qt, QThread, pyqtSignal
    import cv2
    import numpy as np
    from image_processor import process_thermal_image, process_geotiff
    from report_generator import generate_batch_pdf_report, generate_batch_csv_report, generate_geotiff_pdf_report, generate_geotiff_csv_report, generate_kml
    import time
    import rasterio
    from rasterio.windows import Window

    class AnalysisThread(QThread):
        progress_updated = pyqtSignal(int, int, float)  # Current value, total, start time
        analysis_completed = pyqtSignal(list)
        analysis_failed = pyqtSignal(str)

        def __init__(self, image_paths, params, is_geotiff, kml_path=None, tfw_path=None):
            super().__init__()
            self.image_paths = image_paths
            self.params = params
            self.is_geotiff = is_geotiff
            self.kml_path = kml_path
            self.tfw_path = tfw_path

        def run(self):
            try:
                results = []
                if self.is_geotiff:
                    # Process GeoTIFF with optional KML and TFW
                    def progress_callback(value, total, start_time):
                        self.progress_updated.emit(value, total, start_time)

                    processed_image, anomalies, metadata = process_geotiff(
                        self.image_paths[0], self.params, self.kml_path, self.tfw_path, progress_callback
                    )
                    results.append({
                        'image_path': self.image_paths[0],
                        'processed_image': processed_image,
                        'anomalies': anomalies,
                        'metadata': metadata
                    })
                else:
                    # Process R-JPEGs
                    total_images = len(self.image_paths)
                    for i, image_path in enumerate(self.image_paths):
                        processed_image, anomalies, metadata = process_thermal_image(image_path, self.params)
                        results.append({
                            'image_path': image_path,
                            'processed_image': processed_image,
                            'anomalies': anomalies,
                            'metadata': metadata
                        })
                        self.progress_updated.emit(i + 1, total_images, time.time())
                
                self.analysis_completed.emit(results)
            except Exception as e:
                self.analysis_failed.emit(str(e))

    class ReportThread(QThread):
        progress_updated = pyqtSignal(int, float)  # Progress percentage, estimated time remaining
        report_completed = pyqtSignal(str, str)  # Pass PDF and CSV paths back
        report_failed = pyqtSignal(str)

        def __init__(self, results, is_geotiff, kml_path=None, tfw_path=None, output_dir=None):
            super().__init__()
            self.results = results
            self.is_geotiff = is_geotiff
            self.kml_path = kml_path
            self.tfw_path = tfw_path
            self.output_dir = output_dir
            self.start_time = None

        def run(self):
            try:
                self.start_time = time.time()
                total_steps = 4 if self.is_geotiff else 3  # Adjust based on report generation steps
                current_step = 0

                # Step 1: Save processed image
                current_step += 1
                self.progress_updated.emit(int(current_step / total_steps * 100), 0)

                # Step 2: Generate PDF
                if self.is_geotiff:
                    pdf_path = os.path.join(self.output_dir, "Thermal_Analysis_GeoTIFF_Report.pdf")
                    generate_geotiff_pdf_report(pdf_path, self.results[0], kml_path=self.kml_path, tfw_path=self.tfw_path)
                else:
                    pdf_path = os.path.join(self.output_dir, "Thermal_Analysis_Batch_Report.pdf")
                    generate_batch_pdf_report(pdf_path, self.results)

                current_step += 1
                elapsed = time.time() - self.start_time
                eta = (elapsed / current_step) * (total_steps - current_step)
                self.progress_updated.emit(int(current_step / total_steps * 100), eta)

                # Step 3: Generate CSV
                if self.is_geotiff:
                    csv_path = os.path.join(self.output_dir, "GeoTIFF_Anomalies.csv")
                    generate_geotiff_csv_report(csv_path, self.results[0])
                else:
                    csv_path = os.path.join(self.output_dir, "Batch_Anomalies.csv")
                    generate_batch_csv_report(csv_path, self.results)

                current_step += 1
                elapsed = time.time() - self.start_time
                eta = (elapsed / current_step) * (total_steps - current_step)
                self.progress_updated.emit(int(current_step / total_steps * 100), eta)

                # Step 4: Generate KML (only for GeoTIFF, already handled in generate_geotiff_pdf_report)
                if self.is_geotiff:
                    current_step += 1
                    elapsed = time.time() - self.start_time
                    eta = (elapsed / current_step) * (total_steps - current_step)
                    self.progress_updated.emit(int(current_step / total_steps * 100), eta)

                self.progress_updated.emit(100, 0)
                self.report_completed.emit(pdf_path, csv_path)
            except Exception as e:
                self.report_failed.emit(str(e))

    class ThermalAnalysisApp(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Thermal Image Analysis - DJI Mavic 3T (Batch, GeoTIFF, KML, TFW)")
            self.setGeometry(100, 100, 1200, 800)
            
            # Apply gun metal stylesheet
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #2E2E2E;
                }
                QWidget {
                    background-color: #4A4A4A;
                    color: #E0E0E0;
                    font-family: 'Arial';
                    font-size: 12pt;
                }
                QPushButton {
                    background-color: #4A4A4A;
                    color: #E0E0E0;
                    border: 1px solid #B0B0B0;
                    border-radius: 5px;
                    padding: 5px;
                }
                QPushButton:hover {
                    background-color: #00A1D6;
                    color: #FFFFFF;
                    border: 1px solid #00A1D6;
                }
                QPushButton:disabled {
                    background-color: #3A3A3A;
                    color: #808080;
                    border: 1px solid #808080;
                }
                QLineEdit, QComboBox {
                    background-color: #3A3A3A;
                    color: #B0B0B0;
                    border: 1px solid #B0B0B0;
                    border-radius: 3px;
                    padding: 3px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    image: none;
                    width: 10px;
                    height: 10px;
                }
                QProgressBar {
                    background-color: #3A3A3A;
                    border: 1px solid #B0B0B0;
                    border-radius: 5px;
                    text-align: center;
                    color: #E0E0E0;
                }
                QProgressBar::chunk {
                    background-color: #00A1D6;
                    border-radius: 3px;
                }
                QTextEdit {
                    background-color: #3A3A3A;
                    color: #E0E0E0;
                    border: 1px solid #B0B0B0;
                    border-radius: 3px;
                }
                QLabel {
                    color: #E0E0E0;
                }
                QFormLayout QLabel {
                    color: #B0B0B0;
                }
            """)
            
            # Main widget and layout
            self.main_widget = QWidget()
            self.setCentralWidget(self.main_widget)
            self.layout = QHBoxLayout(self.main_widget)
            
            # Left panel: Image display and controls
            self.left_panel = QWidget()
            self.left_layout = QVBoxLayout(self.left_panel)
            
            self.image_label = QLabel("No image loaded")
            self.image_label.setAlignment(Qt.AlignCenter)
            self.image_label.setMinimumSize(600, 400)
            self.left_layout.addWidget(self.image_label)
            
            self.load_file_button = QPushButton("Load Single R-JPEG")
            self.load_file_button.clicked.connect(self.load_single_image)
            self.left_layout.addWidget(self.load_file_button)
            
            self.load_folder_button = QPushButton("Load R-JPEG Folder (Batch)")
            self.load_folder_button.clicked.connect(self.load_folder)
            self.left_layout.addWidget(self.load_folder_button)
            
            self.load_geotiff_button = QPushButton("Load GeoTIFF")
            self.load_geotiff_button.clicked.connect(self.load_geotiff)
            self.left_layout.addWidget(self.load_geotiff_button)
            
            self.load_kml_button = QPushButton("Load KML (Optional)")
            self.load_kml_button.clicked.connect(self.load_kml)
            self.left_layout.addWidget(self.load_kml_button)
            
            self.load_tfw_button = QPushButton("Load TFW (Optional)")
            self.load_tfw_button.clicked.connect(self.load_tfw)
            self.left_layout.addWidget(self.load_tfw_button)
            
            # Parameter inputs
            self.param_layout = QFormLayout()
            self.emissivity_input = QLineEdit("0.95")
            self.distance_input = QLineEdit("5.0")
            self.humidity_input = QLineEdit("0.5")
            self.ref_temp_input = QLineEdit("20.0")
            self.palette_combo = QComboBox()
            self.palette_combo.addItems(["WHITEHOT", "BLACKHOT", "IRONRED", "RAINBOW", "MEDICAL", "ARCTIC", "TYRIAN", "GLOWBOW"])
            self.param_layout.addRow("Emissivity (0.1–1.0):", self.emissivity_input)
            self.param_layout.addRow("Distance (m, 0.1–100):", self.distance_input)
            self.param_layout.addRow("Humidity (0.0–1.0):", self.humidity_input)
            self.param_layout.addRow("Reflected Temp (°C, -40–100):", self.ref_temp_input)
            self.param_layout.addRow("Palette:", self.palette_combo)
            self.left_layout.addLayout(self.param_layout)
            
            self.analyze_button = QPushButton("Analyze")
            self.analyze_button.clicked.connect(self.analyze_images)
            self.analyze_button.setEnabled(False)
            self.left_layout.addWidget(self.analyze_button)
            
            self.report_button = QPushButton("Generate Report")
            self.report_button.clicked.connect(self.generate_report)
            self.report_button.setEnabled(False)
            self.left_layout.addWidget(self.report_button)
            
            self.progress_bar = QProgressBar()
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Progress: %p% | ETA: N/A")
            self.left_layout.addWidget(self.progress_bar)
            
            self.layout.addWidget(self.left_panel)
            
            # Right panel: Analysis results
            self.right_panel = QWidget()
            self.right_layout = QVBoxLayout(self.right_panel)
            
            self.results_text = QTextEdit()
            self.results_text.setReadOnly(True)
            self.right_layout.addWidget(QLabel("Analysis Results:"))
            self.right_layout.addWidget(self.results_text)
            
            self.layout.addWidget(self.right_panel)
            
            # Initialize variables
            self.image_paths = []
            self.kml_path = None
            self.tfw_path = None
            self.is_batch = False
            self.is_geotiff = False
            self.processed_results = []
            self.is_processing = False  # Flag to prevent duplicate processing
            self.start_time = None
        
        def load_single_image(self):
            file_dialog = QFileDialog()
            image_path, _ = file_dialog.getOpenFileName(self, "Select R-JPEG Image", "",
                                                        "Images (*.jpg *.jpeg)")
            if image_path:
                self.image_paths = [image_path]
                self.kml_path = None
                self.tfw_path = None
                self.is_batch = False
                self.is_geotiff = False
                pixmap = QPixmap(image_path).scaled(600, 400, Qt.KeepAspectRatio)
                self.image_label.setPixmap(pixmap)
                self.analyze_button.setEnabled(True)
                self.results_text.setText("Single R-JPEG loaded. Click 'Analyze' to process.")
                self.progress_bar.setValue(0)
                self.progress_bar.setFormat("Progress: %p% | ETA: N/A")
        
        def load_folder(self):
            folder_dialog = QFileDialog()
            folder_path = folder_dialog.getExistingDirectory(self, "Select Folder with R-JPEG Images")
            if folder_path:
                self.image_paths = [os.path.join(folder_path, f) for f in os.listdir(folder_path)
                                    if f.lower().endswith(('.jpg', '.jpeg'))]
                self.kml_path = None
                self.tfw_path = None
                self.is_batch = True
                self.is_geotiff = False
                if self.image_paths:
                    pixmap = QPixmap(self.image_paths[0]).scaled(600, 400, Qt.KeepAspectRatio)
                    self.image_label.setPixmap(pixmap)
                    self.analyze_button.setEnabled(True)
                    self.results_text.setText(f"Loaded {len(self.image_paths)} R-JPEGs. Click 'Analyze' to process batch.")
                else:
                    self.results_text.setText("No valid R-JPEGs found in folder.")
                self.progress_bar.setValue(0)
                self.progress_bar.setFormat("Progress: %p% | ETA: N/A")
        
        def load_geotiff(self):
            file_dialog = QFileDialog()
            geotiff_path, _ = file_dialog.getOpenFileName(self, "Select GeoTIFF File", "",
                                                          "GeoTIFF (*.tif *.tiff)")
            if geotiff_path:
                self.image_paths = [geotiff_path]
                self.kml_path = None
                self.tfw_path = None
                self.is_batch = False
                self.is_geotiff = True
                try:
                    # Use rasterio to load a downsampled version of the GeoTIFF for preview
                    with rasterio.open(geotiff_path) as src:
                        # Get the dimensions of the GeoTIFF
                        width, height = src.width, src.height
                        # Calculate a downsampling factor to fit within the preview size (600x400)
                        downsample_factor = max(width / 600, height / 400)
                        new_width = int(width / downsample_factor)
                        new_height = int(height / downsample_factor)
                        # Read the first band (assuming grayscale) at reduced resolution
                        window = Window(0, 0, width, height)
                        img = src.read(1, window=window, out_shape=(new_height, new_width))
                        # Normalize the image for display (assuming temperature data)
                        if img.max() > 1000:  # Likely Kelvin
                            img = img - 273.15
                        elif img.max() < 100:  # Likely °C
                            img = img * 1.0
                        else:
                            img = img / 10.0
                        # Convert to 8-bit for display
                        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                        # Convert to RGB for display (since QImage expects 3 channels)
                        img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
                        height, width, channel = img.shape
                        bytes_per_line = 3 * width
                        q_image = QImage(img.data, width, height, bytes_per_line, QImage.Format_RGB888)
                        pixmap = QPixmap.fromImage(q_image).scaled(600, 400, Qt.KeepAspectRatio)
                        self.image_label.setPixmap(pixmap)
                    self.analyze_button.setEnabled(True)
                    self.results_text.setText("GeoTIFF loaded. Optionally load KML or TFW, then click 'Analyze' to process.")
                    self.progress_bar.setValue(0)
                    self.progress_bar.setFormat("Progress: %p% | ETA: N/A")
                except Exception as e:
                    self.results_text.setText(f"Error loading GeoTIFF preview: {str(e)}")
                    self.progress_bar.setValue(0)
                    self.progress_bar.setFormat("Progress: %p% | ETA: N/A")
        
        def load_kml(self):
            file_dialog = QFileDialog()
            kml_path, _ = file_dialog.getOpenFileName(self, "Select KML File", "",
                                                      "KML (*.kml)")
            if kml_path:
                if not self.is_geotiff or not self.image_paths:
                    QMessageBox.warning(self, "Warning", "Please load a GeoTIFF first before loading a KML file.")
                    return
                self.kml_path = kml_path
                self.results_text.setText(f"KML loaded: {os.path.basename(kml_path)}. Click 'Analyze' to process with GeoTIFF.")
                self.progress_bar.setValue(0)
                self.progress_bar.setFormat("Progress: %p% | ETA: N/A")
        
        def load_tfw(self):
            file_dialog = QFileDialog()
            tfw_path, _ = file_dialog.getOpenFileName(self, "Select TFW File", "",
                                                      "TFW (*.tfw)")
            if tfw_path:
                if not self.is_geotiff or not self.image_paths:
                    QMessageBox.warning(self, "Warning", "Please load a GeoTIFF first before loading a TFW file.")
                    return
                self.tfw_path = tfw_path
                self.results_text.setText(f"TFW loaded: {os.path.basename(tfw_path)}. Click 'Analyze' to process with GeoTIFF.")
                self.progress_bar.setValue(0)
                self.progress_bar.setFormat("Progress: %p% | ETA: N/A")
        
        def analyze_images(self):
            if not self.image_paths:
                self.results_text.setText("Error: No images loaded.")
                return
            
            if self.is_processing:
                self.results_text.setText("Analysis is already in progress. Please wait.")
                return
            
            self.is_processing = True
            self.analyze_button.setEnabled(False)
            self.report_button.setEnabled(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Progress: %p% | ETA: N/A")
            self.processed_results = []  # Clear previous results
            
            try:
                # Get parameters
                params = {
                    'emissivity': float(self.emissivity_input.text()),
                    'distance': float(self.distance_input.text()),
                    'humidity': float(self.humidity_input.text()),
                    'ref_temp': float(self.ref_temp_input.text()),
                    'palette': self.palette_combo.currentText()
                }
                # Validate parameters
                if not (0.1 <= params['emissivity'] <= 1.0):
                    raise ValueError("Emissivity must be between 0.1 and 1.0")
                if not (0.1 <= params['distance'] <= 100.0):
                    raise ValueError("Distance must be between 0.1 and 100 meters")
                if not (0.0 <= params['humidity'] <= 1.0):
                    raise ValueError("Humidity must be between 0.0 and 1.0")
                if not (-40.0 <= params['ref_temp'] <= 100.0):
                    raise ValueError("Reflected temperature must be between -40 and 100°C")
                
                self.start_time = time.time()
                self.thread = AnalysisThread(self.image_paths, params, self.is_geotiff, self.kml_path, self.tfw_path)
                self.thread.progress_updated.connect(self.update_progress)
                self.thread.analysis_completed.connect(self.on_analysis_completed)
                self.thread.analysis_failed.connect(self.on_analysis_failed)
                self.thread.start()
            
            except Exception as e:
                self.results_text.setText(f"Error during analysis setup: {str(e)}")
                self.progress_bar.setValue(0)
                self.progress_bar.setFormat("Progress: %p% | ETA: N/A")
                self.is_processing = False
                self.analyze_button.setEnabled(True)
        
        def update_progress(self, value, total, start_time):
            percentage = (value / total) * 100
            self.progress_bar.setValue(int(percentage))
            elapsed = time.time() - start_time
            if value > 0:
                eta = elapsed * (total / value - 1)
            else:
                eta = 0
            eta_str = f"{int(eta)}s" if eta > 0 else "N/A"
            self.progress_bar.setFormat(f"Progress: %p% | ETA: {eta_str}")
            QApplication.processEvents()
        
        def on_analysis_completed(self, results):
            self.processed_results = results
            total_anomalies = sum(len(result['anomalies']) for result in self.processed_results)
            result_text = f"Processing complete.\nProcessed {len(self.processed_results)} {'GeoTIFF' if self.is_geotiff else 'R-JPEG(s)'}.\n"
            result_text += f"Total anomalies detected: {total_anomalies}\n"
            for result in self.processed_results:
                result_text += f"\n{os.path.basename(result['image_path'])}: {len(result['anomalies'])} anomalies\n"
                for i, anomaly in enumerate(result['anomalies']):
                    result_text += f"  Anomaly {i+1}: Center at ({anomaly['center_x']}, {anomaly['center_y']}), "
                    result_text += f"Max Temp: {anomaly['max_temp']:.1f}°C"
                    if 'latitude' in anomaly and 'longitude' in anomaly:
                        result_text += f", Lat/Lon: ({anomaly['latitude']:.6f}, {anomaly['longitude']:.6f})"
                    result_text += "\n"
            self.results_text.setText(result_text)
            
            # Update display with the last processed image
            if self.processed_results:
                processed_image = self.processed_results[-1]['processed_image']
                height, width, channel = processed_image.shape
                bytes_per_line = 3 * width
                q_image = QImage(processed_image.data, width, height, bytes_per_line, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(q_image).scaled(600, 400, Qt.KeepAspectRatio)
                self.image_label.setPixmap(pixmap)
            
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("Progress: 100% | ETA: 0s")
            self.report_button.setEnabled(True)
            self.is_processing = False
            self.analyze_button.setEnabled(True)
            QApplication.processEvents()
        
        def on_analysis_failed(self, error):
            self.results_text.setText(f"Error during analysis: {error}")
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Progress: %p% | ETA: N/A")
            self.is_processing = False
            self.analyze_button.setEnabled(True)
            QApplication.processEvents()
        
        def generate_report(self):
            if not self.processed_results:
                self.results_text.setText("Error: No analysis results available.")
                return
            
            self.is_processing = True
            self.report_button.setEnabled(False)
            self.analyze_button.setEnabled(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Progress: %p% | ETA: N/A")
            
            # Prompt user to select output directory
            output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory for Reports", ".")
            if not output_dir:
                self.results_text.setText("Report generation cancelled: No output directory selected.")
                self.is_processing = False
                self.report_button.setEnabled(True)
                self.analyze_button.setEnabled(True)
                self.progress_bar.setValue(0)
                self.progress_bar.setFormat("Progress: %p% | ETA: N/A")
                return
            
            self.report_thread = ReportThread(self.processed_results, self.is_geotiff, self.kml_path, self.tfw_path, output_dir)
            self.report_thread.progress_updated.connect(self.update_report_progress)
            self.report_thread.report_completed.connect(self.on_report_completed)
            self.report_thread.report_failed.connect(self.on_report_failed)
            self.report_thread.start()
        
        def update_report_progress(self, percentage, eta):
            self.progress_bar.setValue(percentage)
            eta_str = f"{int(eta)}s" if eta > 0 else "0s"
            self.progress_bar.setFormat(f"Progress: %p% | ETA: {eta_str}")
            QApplication.processEvents()
        
        def on_report_completed(self, pdf_path, csv_path):
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("Progress: 100% | ETA: 0s")
            self.results_text.append(f"\nReport generated:\nPDF: {pdf_path}\nCSV: {csv_path}")
            self.is_processing = False
            self.report_button.setEnabled(True)
            self.analyze_button.setEnabled(True)
            QApplication.processEvents()
        
        def on_report_failed(self, error):
            self.results_text.setText(f"Error generating report: {error}")
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Progress: %p% | ETA: N/A")
            self.is_processing = False
            self.report_button.setEnabled(True)
            self.analyze_button.setEnabled(True)
            QApplication.processEvents()

    # Debug print to confirm this point is reached
    print("Creating window...")
    window = ThermalAnalysisApp()
    print("Window created. Showing window...")
    window.show()
    print("Window shown. Starting app...")
    sys.exit(app.exec_())