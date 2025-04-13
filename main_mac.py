import os
import sys
import time
import uuid
import json
import requests
# import win32print
# import win32api
import firebase_admin
from firebase_admin import credentials, db
import threading
import queue
import socket
import platform
import logging
from concurrent.futures import ThreadPoolExecutor
import subprocess
from PySide2.QtCore import Qt, Signal, QObject, QThreadPool, QRunnable, QTimer
from PySide2.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QFrame, QScrollArea,
                               QProgressBar, QTextEdit, QGridLayout, QSystemTrayIcon, 
                               QMenu, QAction, QMessageBox, QSizePolicy)
from PySide2.QtGui import QIcon, QColor
from qt_material import apply_stylesheet

sumatra_path = os.path.join(os.path.dirname(__file__), "SumatraPDF.exe")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("printer_app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# ------------------ Firebase Initialization ------------------
def init_firebase():
    """Initialize Firebase connection using service account credentials."""
    try:
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        cred_path = os.getenv("FIREBASE_CRED_PATH", os.path.join(base_path, "serviceAccountKey.json"))
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://admin-panel-printer-default-rtdb.europe-west1.firebasedatabase.app"
        })
        logging.info("Firebase initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Firebase: {e}")
        raise

# ------------------ Printer Management ------------------
def get_printers():
    """Retrieve list of installed printers (local and network)."""
    try:
        # printers_local = [printer[2] for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
        # printers_network = [printer[2] for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_NETWORK)]
        # printers = list(set(printers_local + printers_network))
        # if not printers:
        #     logging.warning("No printers found.")
        return ""
    except Exception as e:
        logging.error(f"Error retrieving printers: {e}")
        return []

def update_printer_list(user_id):
    """Update printer list in Firebase and return it."""
    try:
        printers = get_printers()
        users_ref = db.reference("users")
        user_snapshot = users_ref.order_by_child("token").equal_to(user_id).get()
        if not user_snapshot:
            logging.error(f"No user found with token: {user_id}")
            return []
        user_info = next(iter(user_snapshot.values()))
        user = user_info['id']
        db.reference(f"users/{user}/printers").set(printers)
        logging.info(f"Printer list updated for user {user_id}.")
        return printers
    except Exception as e:
        logging.error(f"Error updating printer list: {e}")
        return []

def update_connection_status(user_id, status):
    """Update device connection status in Firebase."""
    try:
        users_ref = db.reference("users")
        user_snapshot = users_ref.order_by_child("token").equal_to(user_id).get()
        user_info = next(iter(user_snapshot.values()))
        user = user_info['id']
        db.reference(f"users/{user}").update({"connected": status})
        logging.info(f"Connection status for user {user_id} set to {status}.")
    except Exception as e:
        logging.error(f"Error updating connection status: {e}")

# ------------------ File Download and Printing ------------------
def load_config():
    """Load configuration from config.json."""
    try:
        with open("config.json", "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        raise

def download_file(url, save_path, progress_callback, timeout=30):
    """Download a file from a URL with progress tracking."""
    try:
        headers = {"Accept": "application/pdf"}
        response = requests.get(url, headers=headers, stream=True, timeout=timeout)
        if response.status_code != 200:
            raise Exception(f"Download failed with status code: {response.status_code}")
        total_size = int(response.headers.get("content-length", 0))
        downloaded = 0
        with open(save_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    progress_callback(downloaded / total_size)
        logging.info(f"File downloaded successfully: {save_path}")
    except Exception as e:
        logging.error(f"Error downloading file: {e}")
        raise

def download_pdf_from_url(file_url, file_key, progress_callback, dest_dir="downloads"):
    """Download a PDF file based on file_key."""
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
    """Print a PDF file with specified printer settings."""
    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return False
    return auto_print_pdf(file_path, settings)

def auto_print_pdf(file_path, settings):
    """Automatically print a PDF with optional DEVMODE settings."""
    # printer_name = settings.get("namePrinter", win32print.GetDefaultPrinter())
    # COOMEND = f"{settings.get('colorMode')},{settings.get('orientation')},paper={settings.get('paperSize')},"
    try:
        # if not os.path.exists(sumatra_path):
        #     raise FileNotFoundError("SumatraPDF not found")
        # subprocess.run([
        #     sumatra_path,
        #     "-print-to", printer_name,
        #     "-silent",
        #     "-print-settings", COOMEND,
        #     file_path
        # ], check=True)
        # logging.info(f"پرینت موفق برای {file_path} روی {printer_name}")
        return True
    except Exception as e:
        logging.error(f"خطا هنگام پرینت: {e}")
        return False

# ------------------ Token Management ------------------
def save_token(token):
    """Save token to a local file."""
    try:
        with open("token.txt", "w") as f:
            f.write(token)
        logging.info("Token saved successfully.")
    except Exception as e:
        logging.error(f"Error saving token: {e}")

def load_token():
    """Load token from a local file."""
    try:
        if os.path.exists("token.txt"):
            with open("token.txt", "r") as f:
                return f.read().strip()
        return None
    except Exception as e:
        logging.error(f"Error loading token: {e}")
        return None

# ------------------ System Information ------------------
def get_system_info():
    """Collect system information including IP and geolocation."""
    try:
        public_ip = requests.get("https://api.ipify.org", timeout=5).text
        location_data = requests.get(f"https://ipinfo.io/{public_ip}/json", timeout=5).json()
    except Exception as e:
        logging.error(f"Error retrieving IP or location: {e}")
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
    """Upload system information to Firebase for support."""
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

# ------------------ GUI Application ------------------
class PrinterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.stop_event = threading.Event()
        self.update_queue = queue.Queue()
        self.printers = []
        self.jobs = {}
        self.user_id = None
        self.listener = None
        self.listenerUpdate = None

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
        self.jobs_table = QFrame()
        self.jobs_table_layout = QGridLayout(self.jobs_table)
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

        # System tray setup (assuming an icon file "icon.png" exists)
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

        # Load token
        token = load_token()
        if token:
            self.token_entry.setText(token)
            self.on_connect()

    def closeEvent(self, event):
        """Minimize to system tray instead of closing."""
        self.hide()
        event.ignore()
        self.update_queue.put({'type': 'log', 'message': "Application minimized to system tray."})

    def clear_layout(self, layout):
        """Clear all widgets from a layout."""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def check_update_queue(self):
        """Update UI based on queued messages."""
        while not self.update_queue.empty():
            message = self.update_queue.get()
            if message['type'] == 'log':
                self.log_textbox.append(message['message'])
            elif message['type'] == 'progress':
                progress_bar = message['progress_bar']
                try:
                    progress_bar.setValue(int(message['value'] * 100))
                except Exception as e:
                    print(f"Error updating progress bar: {e}")
            elif message['type'] == 'print_jobs':
                self.update_print_jobs_ui(message['jobs'])

    def on_connect(self):
      
        """Validate token and initiate connection."""
        print(self)
        print(str(self.token_entry.text()))
        token = str(self.token_entry.text())
        if not token:
            from PySide2.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", "Please enter a valid token!")
            return
        print("threading")  
        threading.Thread(target=self.connect_to_printer, args=(token,), daemon=True).start()

    def connect_to_printer(self, token):
        """Connect to Firebase and start processing jobs."""
        try:
            print("connect_to_printer")
            users_ref = db.reference("users")
            print(users_ref)
            user_snapshot = users_ref.order_by_child("token").equal_to(token).get()
            if not user_snapshot:
                from PySide2.QtWidgets import QMessageBox
                QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Error", "Invalid token!"))
                return
            user_info = next(iter(user_snapshot.values()))
            self.user_id = token
            update_connection_status(self.user_id, True)
            upload_system_info(self.user_id)
            self.printers = update_printer_list(self.user_id)
            QTimer.singleShot(0, self.update_ui_after_connect)
            save_token(token)
            self.listenerUpdate = db.reference("users").listen(self.check_connection_status)
            self.listener = db.reference(f"print_jobs/{self.user_id}").listen(self.print_jobs_callback)
        except Exception as e:
            print(e)
            self.update_queue.put({'type': 'log', 'message': f"Connection error: {e}"})

    def update_ui_after_connect(self):
        """Update UI after successful connection."""
        self.status_label.setText("Connected")
        self.main_frame.show()
        self.display_printers(self.printers)
        self.update_queue.put({'type': 'log', 'message': "Connected successfully."})

    def display_printers(self, printers):
        """Display list of printers in UI."""
        self.clear_layout(self.printers_list_layout)
        for printer in printers:
            frame = QFrame()
            layout = QHBoxLayout(frame)
            label = QLabel(printer)
            layout.addWidget(label)
            status_label = QLabel("Online")
            layout.addWidget(status_label)
            self.printers_list_layout.addWidget(frame)

    def refresh_printers(self):
        """Refresh the printer list."""
        if self.user_id:
            self.printers = update_printer_list(self.user_id)
            self.display_printers(self.printers)
            self.update_queue.put({'type': 'log', 'message': "Printer list refreshed."})

    def check_connection_status(self, event):
        """Update device connection status in Firebase."""
        try:
            users_ref = db.reference("users")
            user_snapshot = users_ref.order_by_child("token").equal_to(self.user_id).get()
            if not user_snapshot:
                save_token('')
                self.status_label.setText("Disconnected")
                from PySide2.QtWidgets import QMessageBox
                QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Error", "Invalid token!"))
                return
        except Exception as e:
            logging.error(f"Error updating connection status: {e}")

    def print_jobs_callback(self, event):
        """Handle print job updates from Firebase."""
        jobs_ref = db.reference(f"print_jobs/{self.user_id}")
        jobs = jobs_ref.get()
        if not jobs:
            return
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
        """Process a single print job with progress bar."""
        log = lambda msg: self.update_queue.put({'type': 'log', 'message': msg})
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        row = self.jobs_table_layout.rowCount()
        self.jobs_table_layout.addWidget(progress_bar, row, 0, 1, 5)

        try:
            def update_progress(value):
                self.update_queue.put({
                    'type': 'progress',
                    'progress_bar': progress_bar,
                    'value': value
                })

            local_file = download_pdf_from_url(
                job.get("file_url"),
                job.get("file_key"),
                update_progress
            )
            success = print_pdf(job, local_file)

            db.reference(f"print_jobs/{self.user_id}/{job_id}").update({
                "status": "completed" if success else "failed",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
            log(f"Print job {job_id} {'completed' if success else 'failed'}.")
        except Exception as e:
            log(f"Error processing job {job_id}: {e}")
            db.reference(f"print_jobs/{self.user_id}/{job_id}").update({
                "status": "failed",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
        finally:
            QTimer.singleShot(1000, progress_bar.deleteLater)

    def update_print_jobs_ui(self, jobs):
        """Update the print jobs table in UI."""
        self.clear_layout(self.jobs_table_layout)
        headers = ["Job ID", "Printer", "Status", "Timestamp", "Action"]
        for col, header in enumerate(headers):
            label = QLabel(header)
            self.jobs_table_layout.addWidget(label, 0, col)
        if jobs and isinstance(jobs, dict):
            for i, (job_id, job) in enumerate(jobs.items(), start=1):
                self.jobs_table_layout.addWidget(QLabel(job_id), i, 0)
                self.jobs_table_layout.addWidget(QLabel(job.get('namePrinter', 'N/A')), i, 1)
                status = job.get('status', 'N/A')
                status_label = QLabel(status.capitalize())
                self.jobs_table_layout.addWidget(status_label, i, 2)
                self.jobs_table_layout.addWidget(QLabel(job.get('timestamp', 'N/A')), i, 3)
                if status == "pending":
                    cancel_btn = QPushButton("Cancel")
                    cancel_btn.clicked.connect(lambda checked, j=job_id: self.cancel_job(j))
                    self.jobs_table_layout.addWidget(cancel_btn, i, 4)
        else:
            label = QLabel("No active print jobs")
            self.jobs_table_layout.addWidget(label, 1, 0, 1, 5)

    def cancel_job(self, job_id):
        """Cancel a print job."""
        try:
            db.reference(f"print_jobs/{self.user_id}/{job_id}").update({
                "status": "canceled",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            })
            self.update_queue.put({'type': 'log', 'message': f"Print job {job_id} canceled."})
        except Exception as e:
            self.update_queue.put({'type': 'log', 'message': f"Error canceling job {job_id}: {e}"})

    def quit_app(self):
        """Cleanly exit the application."""
        self.stop_event.set()
        if self.listener:
            self.listener.close()
        if self.user_id:
            update_connection_status(self.user_id, False)
        self.tray_icon.hide()
        QApplication.quit()

# ------------------ Main Execution ------------------
if __name__ == "__main__":
    init_firebase()
    app = QApplication(sys.argv)
    apply_stylesheet(app, theme='dark_teal.xml')
    window = PrinterApp()
    window.show()
    sys.exit(app.exec_())
