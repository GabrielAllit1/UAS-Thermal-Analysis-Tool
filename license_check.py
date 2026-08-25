import sys
import os
import datetime
import json
import base64
import hmac
import hashlib
from PyQt5.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLineEdit, QPushButton, QLabel
from PyQt5.QtCore import QCoreApplication, QUrl
from PyQt5.QtGui import QDesktopServices

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