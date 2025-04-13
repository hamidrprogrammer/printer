import os
import sys
import time
import uuid
import json
import requests
import subprocess
import threading
import queue
import socket
import platform
import logging
from PySide2.QtCore import Qt, Signal, QTimer
from PySide2.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QScrollArea,
    QProgressBar, QTextEdit, QGridLayout, QSystemTrayIcon,
    QMenu, QAction, QMessageBox, QTableWidget, QTableWidgetItem
)
from PySide2.QtGui import QIcon
from qt_material import apply_stylesheet
import firebase_admin
from firebase_admin import credentials, db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("printer_app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# Firebase Initialization
def init_firebase():
    """Initialize Firebase with the service account credentials."""
    try:
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        cred_path = os.getenv("FIREBASE_CRED_PATH", os.path.join(base_path, "admin-panel.json"))
        if not os.path.exists(cred_path):
            raise FileNotFoundError(f"Firebase credential file not found at {cred_path}")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://admin-panel-printer-default-rtdb.europe-west1.firebasedatabase.app"
        })
        logging.info("Firebase initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Firebase: {e}")
        raise

# Printer Management
def get_printers():
    """Retrieve the list of available printers using lpstat on macOS."""
    try:
        result = subprocess.run(["lpstat", "-p"], capture_output=True, text=True, check=True)
        lines = result.stdout.splitlines()
        printers = []
        for line in lines:
            if line.startswith("printer"):
                parts = line.split()
                if len(parts) > 1:
                    printers.append(parts[1])
        return printers
    except subprocess.CalledProcessError as e:
        logging.error(f"Error retrieving printers: {e}")
        return []

def update_connection_status(user_id, status):
    """Update the connection status of the user in Firebase."""
    try:
        users_ref = db.reference("users")
        user_snapshot = users_ref.order_by_child("token").equal_to(user_id).get()
        user_info = next(iter(user_snapshot.values()))
        user = user_info['id']
        db.reference(f"users/{user}").update({"connected": status})
        logging.info(f"Connection status for user {user_id} set to {status}.")
    except Exception as e:
        logging.error(f"Error updating connection status: {e}")

# File Download and Printing
def download_file(url, save_path, progress_callback, timeout=30):
    """Download a file from a URL with progress updates."""
    try:
        headers = {"Accept": "application/pdf"}
        response = requests.get(url, headers=headers, stream=True, timeout=timeout)
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0
        with open(save_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress_callback(downloaded / total_size)
        logging.info(f"File downloaded successfully: {save_path}")
    except Exception as e:
        logging.error(f"Error downloading file: {e}")
        raise

def download_pdf_from_url(file_url, file_key, progress_callback, dest_dir="downloads"):
    """Download a PDF from a URL and save it locally."""
    try:
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        local_file = os.path.join(os.path.abspath(dest_dir), f"{file_key}.pdf")
        download_file(file_url, local_file, progress_callback)
        return local_file
    except Exception as e:
        logging.error(f"Error downloading PDF: {e}")
        raise

def print_pdf(settings, file_path):
    """Print a PDF file using the lp command on macOS."""
    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return False
    printer_name = settings.get("namePrinter")
    if not printer_name:
        logging.error("No printer specified.")
        return False
    cmd = ["lp", "-d", printer_name, file_path]
    if "orientation" in settings:
        orientation = settings["orientation"].lower()
        if orientation == "landscape":
            cmd.extend(["-o", "landscape"])
        elif orientation == "portrait":
            cmd.extend(["-o", "portrait"])
    if "paperSize" in settings:
        paper_size = settings["paperSize"]
        cmd.extend(["-o", f"media={paper_size}"])
    if "copies" in settings:
        copies = settings["copies"]
        cmd.extend(["-n", str(copies)])
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logging.info(f"Print job sent to {printer_name} for {file_path}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error printing file: {e.stderr}")
        return False

# Token Management
def save_token(token):
    """Save the connection token to a file."""
    try:
        with open("token.txt", "w") as f:
            f.write(token)
        logging.info("Token saved successfully.")
    except Exception as e:
        logging.error(f"Error saving token: {e}")

def load_token():
    """Load the connection token from a file."""
    try:
        if os.path.exists("token.txt"):
            with open("token.txt", "r") as f:
                return f.read().strip()
        return None
    except Exception as e:
        logging.error(f"Error loading token: {e}")
        return None

# System Information
def get_system_info():
    """Collect system information including IP and location."""
    try:
        public_ip = requests.get("https://api.ipify.org", timeout=5).text
        location_data = requests.get(f"https://ipinfo.io/{public_ip}/json", timeout=5).json()
    except Exception:
        public_ip = "Unknown"
        location_data = {}
    return {
        "hostname": socket.gethostname(),
        "ip": socket.gethostbyname(socket.gethostname()),
        "public_ip": public_ip,
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "uuid": str(uuid.uuid1()),
        "location": {
            "city": location_data.get("city", "Unknown"),
            "region": location_data.get("region", "Unknown"),
            "country": location_data.get("country", "Unknown"),
            "loc": location_data.get("loc", "Unknown"),
            "org": location_data.get("org", "Unknown"),
            "timezone": location_data.get("timezone", "Unknown")
        }
    }

def upload_system_info(user_id):
    """Upload system information to Firebase."""
    try:
        system_info = get_system_info()
        users_ref = db.reference("users")
        user_snapshot = users_ref.order_by_child("token").equal_to(user_id).get()
        user_info = next(iter(user_snapshot.values()))
        user = user_info['id']
        db.reference(f"users/{user}/system_info").set(system_info)
        logging.info(f"System info uploaded for user {user_id}.")
    except Exception as e:
        logging.error(f"Error uploading system info: {e}")

# GUI Application
class PrinterApp(QWidget):
    """Main application window for the printer application."""
    connection_success = Signal()
    show_error = Signal(str)

    def __init__(self):
        super().__init__()
        self.stop_event = threading.Event()
        self.update_queue = queue.Queue()
        self.printers = []
        self.jobs = {}
        self.user_id = None
        self.user_key = None  # Added to store Firebase user key
        self.listener = None
        self.listener_update = None
        self.progress_bars = {}

        # Window setup
        self.setWindowTitle("PrinterSync Pro")
        self.resize(1000, 800)
        self.setMinimumSize(800, 600)

        # Main layout
        main_layout = QGridLayout(self)
        main_layout.setColumnStretch(0, 1)
        main_layout.setRowStretch(3, 1)

        # Header
        header_frame = QFrame()
        header_layout = QVBoxLayout(header_frame)
        self.title_label = QLabel("PrinterSync Pro")
        header_layout.addWidget(self.title_label)
        main_layout.addWidget(header_frame, 0, 0)

        # Token input
        token_frame = QFrame()
        token_layout = QVBoxLayout(token_frame)
        token_label = QLabel("Enter Connection Token:")
        token_layout.addWidget(token_label)
        self.token_entry = QLineEdit()
        self.token_entry.setPlaceholderText("Paste your token here")
        token_layout.addWidget(self.token_entry)
        self.submit_button = QPushButton("Connect")
        self.submit_button.clicked.connect(self.on_connect)
        token_layout.addWidget(self.submit_button)
        main_layout.addWidget(token_frame, 1, 0)

        # Connection status
        status_frame = QFrame()
        status_layout = QVBoxLayout(status_frame)
        self.status_label = QLabel("Disconnected")
        status_layout.addWidget(self.status_label)
        main_layout.addWidget(status_frame, 2, 0)

        # Main content
        self.main_frame = QFrame()
        main_grid = QGridLayout(self.main_frame)
        main_grid.setColumnStretch(0, 1)
        main_grid.setColumnStretch(1, 1)
        main_grid.setRowStretch(2, 1)

        # Printers section
        self.printers_frame = QFrame()
        printers_layout = QVBoxLayout(self.printers_frame)
        printers_label = QLabel("Available Printers")
        printers_layout.addWidget(printers_label)
        self.printers_scroll = QScrollArea()
        self.printers_scroll.setWidgetResizable(True)
        self.printers_list_widget = QWidget()
        self.printers_list_layout = QVBoxLayout(self.printers_list_widget)
        self.printers_scroll.setWidget(self.printers_list_widget)
        printers_layout.addWidget(self.printers_scroll)
        self.refresh_button = QPushButton("Refresh Printers")
        self.refresh_button.clicked.connect(self.refresh_printers)
        printers_layout.addWidget(self.refresh_button)
        main_grid.addWidget(self.printers_frame, 0, 0)

        # Print jobs section
        self.jobs_frame = QFrame()
        jobs_layout = QVBoxLayout(self.jobs_frame)
        jobs_label = QLabel("Print Jobs")
        jobs_layout.addWidget(jobs_label)
        self.jobs_table = QTableWidget()
        self.jobs_table.setColumnCount(6)
        self.jobs_table.setHorizontalHeaderLabels(["Job ID", "Printer", "Status", "Progress", "Timestamp", "Action"])
        self.jobs_table.horizontalHeader().setStretchLastSection(True)
        jobs_layout.addWidget(self.jobs_table)
        main_grid.addWidget(self.jobs_frame, 1, 0, 2, 1)

        # Log section
        self.log_frame = QFrame()
        log_layout = QVBoxLayout(self.log_frame)
        log_label = QLabel("Event Log")
        log_layout.addWidget(log_label)
        self.log_textbox = QTextEdit()
        self.log_textbox.setReadOnly(True)
        log_layout.addWidget(self.log_textbox)
        main_grid.addWidget(self.log_frame, 0, 1, 3, 1)

        main_layout.addWidget(self.main_frame, 3, 0)
        self.main_frame.hide()

        # System tray setup
        self.tray_icon = QSystemTrayIcon(QIcon("icon.png"), self)
        menu = QMenu()
        show_action = menu.addAction("Show App")
        show_action.triggered.connect(self.show)
        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(self.quit_app)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

        # QTimer for checking update queue
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_update_queue)
        self.timer.start(100)

        # QTimer for checking printer changes
        self.printer_timer = QTimer(self)
        self.printer_timer.timeout.connect(self.check_printers)

        # Connect signals
        self.connection_success.connect(self.update_ui_after_connect)
        self.show_error.connect(self.show_error_message)

        # Load token
        token = load_token()
        if token:
            self.token_entry.setText(token)
            self.on_connect()

    def show_error_message(self, message):
        """Display an error message dialog."""
        QMessageBox.critical(self, "Error", message)

    def closeEvent(self, event):
        """Minimize to system tray on window close."""
        self.hide()
        event.ignore()
        self.update_queue.put({'type': 'log', 'message': "Application minimized to system tray."})

    def on_connect(self):
        """Initiate connection to Firebase with the provided token."""
        token = self.token_entry.text().strip()
        if not token:
            self.show_error.emit("Please enter a valid token!")
            return
        threading.Thread(target=self.connect_to_printer, args=(token,), daemon=True).start()

    def connect_to_printer(self, token):
        """Connect to Firebase and set up listeners."""
        try:
            users_ref = db.reference("users")
            user_snapshot = users_ref.order_by_child("token").equal_to(token).get()
            if not user_snapshot:
                self.show_error.emit("Invalid token!")
                return
            self.user_key = next(iter(user_snapshot.keys()))
            self.user_id = token
            update_connection_status(self.user_id, True)
            upload_system_info(self.user_id)
            self.printers = get_printers()
            db.reference(f"users/{self.user_key}/printers").set(self.printers)
            self.connection_success.emit()
            save_token(token)
            self.listener_update = db.reference("users").listen(self.check_connection_status)
            self.listener = db.reference(f"print_jobs/{self.user_id}").listen(self.print_jobs_callback)
        except Exception as e:
            self.update_queue.put({'type': 'log', 'message': f"Connection error: {e}"})

    def update_ui_after_connect(self):
        """Update the UI after a successful connection."""
        self.status_label.setText("Connected")
        self.main_frame.show()
        self.display_printers(self.printers)
        self.update_queue.put({'type': 'log', 'message': "Connected successfully."})
        self.printer_timer.start(10000)

    def set_printers_in_firebase(self, printers):
        """Set the printer list in Firebase."""
        try:
            db.reference(f"users/{self.user_key}/printers").set(printers)
            self.update_queue.put({'type': 'log', 'message': "Printer list updated in Firebase."})
        except Exception as e:
            self.update_queue.put({'type': 'log', 'message': f"Error updating printer list: {e}"})

    def check_printers(self):
        """Check for changes in the printer list and update if necessary."""
        new_printers = get_printers()
        if new_printers != self.printers:
            self.printers = new_printers
            self.set_printers_in_firebase(new_printers)
            self.display_printers(new_printers)

    def display_printers(self, printers):
        """Display the list of available printers in the scroll area."""
        while self.printers_list_layout.count():
            child = self.printers_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        for printer in printers:
            frame = QFrame()
            layout = QHBoxLayout(frame)
            label = QLabel(printer)
            layout.addWidget(label)
            status_label = QLabel("Online")  # Simplified status
            layout.addWidget(status_label)
            self.printers_list_layout.addWidget(frame)

    def refresh_printers(self):
        """Refresh the list of printers."""
        if self.user_key:
            self.printers = get_printers()
            self.set_printers_in_firebase(self.printers)
            self.display_printers(self.printers)
            self.update_queue.put({'type': 'log', 'message': "Printer list refreshed."})

    def check_connection_status(self, event):
        """Check and maintain connection status."""
        try:
            if not self.user_id:
                return
            users_ref = db.reference("users")
            user_snapshot = users_ref.order_by_child("token").equal_to(self.user_id).get()
            if not user_snapshot:
                save_token('')
                self.status_label.setText("Disconnected")
                self.show_error.emit("Invalid token!")
                self.main_frame.hide()
                self.printer_timer.stop()
        except Exception as e:
            logging.error(f"Error checking connection status: {e}")

    def print_jobs_callback(self, event):
        """Handle updates to print jobs from Firebase."""
        if not self.user_id:
            return
        jobs_ref = db.reference(f"print_jobs/{self.user_id}")
        jobs = jobs_ref.get()
        if jobs:
            self.jobs = jobs
            self.update_queue.put({'type': 'print_jobs', 'jobs': self.jobs})
            for job_id, job in self.jobs.items():
                if job.get("status") == "pending":
                    threading.Thread(
                        target=self.process_single_job,
                        args=(job_id, job),
                        daemon=True
                    ).start()

    def process_single_job(self, job_id, job):
        """Process a single print job in a separate thread."""
        log = lambda msg: self.update_queue.put({'type': 'log', 'message': msg})
        try:
            def update_progress(value):
                self.update_queue.put({'type': 'progress', 'job_id': job_id, 'value': value})

            local_file = download_pdf_from_url(
                job.get("file_url"),
                job.get("file_key"),
                update_progress
            )
            success = print_pdf(job, local_file)
            new_status = "completed" if success else "failed"
            db.reference(f"print_jobs/{self.user_id}/{job_id}").update({
                "status": new_status,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
            log(f"Print job {job_id} {new_status}.")
        except Exception as e:
            log(f"Error processing job {job_id}: {e}")
            db.reference(f"print_jobs/{self.user_id}/{job_id}").update({
                "status": "failed",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
        finally:
            self.update_queue.put({'type': 'job_finished', 'job_id': job_id})

    def update_print_jobs_ui(self, jobs):
        """Update the print jobs table with current job data."""
        self.jobs_table.setRowCount(0)
        for row, (job_id, job) in enumerate(jobs.items()):
            self.jobs_table.insertRow(row)
            self.jobs_table.setItem(row, 0, QTableWidgetItem(job_id))
            self.jobs_table.setItem(row, 1, QTableWidgetItem(job.get('namePrinter', 'N/A')))
            status = job.get('status', 'N/A')
            self.jobs_table.setItem(row, 2, QTableWidgetItem(status.capitalize()))
            timestamp = job.get('timestamp', 'N/A')
            self.jobs_table.setItem(row, 4, QTableWidgetItem(timestamp))
            if status == "pending":
                progress_bar = QProgressBar()
                progress_bar.setRange(0, 100)
                self.jobs_table.setCellWidget(row, 3, progress_bar)
                self.progress_bars[job_id] = progress_bar
                cancel_btn = QPushButton("Cancel")
                cancel_btn.clicked.connect(lambda checked, j=job_id: self.cancel_job(j))
                self.jobs_table.setCellWidget(row, 5, cancel_btn)
            else:
                self.jobs_table.setItem(row, 3, QTableWidgetItem("N/A"))
                self.jobs_table.setItem(row, 5, QTableWidgetItem(""))

    def cancel_job(self, job_id):
        """Cancel a pending print job."""
        try:
            db.reference(f"print_jobs/{self.user_id}/{job_id}").update({
                "status": "canceled",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
            self.update_queue.put({'type': 'log', 'message': f"Print job {job_id} canceled."})
        except Exception as e:
            self.update_queue.put({'type': 'log', 'message': f"Error canceling job {job_id}: {e}"})

    def check_update_queue(self):
        """Process messages from the update queue to update the UI."""
        while not self.update_queue.empty():
            message = self.update_queue.get()
            msg_type = message['type']
            if msg_type == 'log':
                self.log_textbox.append(message['message'])
            elif msg_type == 'progress':
                job_id = message['job_id']
                value = message['value']
                if job_id in self.progress_bars:
                    self.progress_bars[job_id].setValue(int(value * 100))
            elif msg_type == 'job_finished':
                job_id = message['job_id']
                if job_id in self.progress_bars:
                    progress_bar = self.progress_bars.pop(job_id)
                    progress_bar.setValue(100)
            elif msg_type == 'print_jobs':
                self.update_print_jobs_ui(message['jobs'])

    def quit_app(self):
        """Cleanly exit the application."""
        self.stop_event.set()
        if self.listener:
            self.listener.close()
        if self.listener_update:
            self.listener_update.close()
        if self.user_id:
            update_connection_status(self.user_id, False)
        self.printer_timer.stop()
        self.tray_icon.hide()
        QApplication.quit()

# Main Execution
if __name__ == "__main__":
    init_firebase()
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme='dark_teal.xml')
    window = PrinterApp()
    window.show()
    sys.exit(app.exec_())
