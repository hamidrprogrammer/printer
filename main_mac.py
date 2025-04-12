import toga
import threading
import queue
import time
import uuid
import json
import requests
import cups
import firebase_admin
from firebase_admin import credentials, db
import logging
import os
import sys
import tempfile
from PIL import Image
from toga.style import Pack
from toga.style.pack import COLUMN, ROW
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("printer_app.log"), logging.StreamHandler(sys.stdout)]
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
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred, {
            "databaseURL": "https://admin-panel-printer-default-rtdb.europe-west1.firebasedatabase.app"
        })
        logging.info("Firebase initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Firebase: {e}")
        raise

# ------------------ Printer Management ------------------
def get_printers():
    """Retrieve list of installed printers."""
    try:
        conn = cups.Connection()
        printers = list(conn.getPrinters().keys())
        if not printers:
            logging.warning("No printers found.")
        return printers
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
    """Automatically print a PDF with optional settings for macOS."""
    printer_name = settings.get("namePrinter", "")
    if not printer_name:
        conn = cups.Connection()
        printers = conn.getPrinters()
        if printers:
            printer_name = list(printers.keys())[0]
        else:
            logging.error("No printers available")
            return False
    try:
        conn = cups.Connection()
        options = {}
        color_mode = settings.get("colorMode", "").lower()
        if color_mode == "color":
            options['ColorModel'] = 'RGB'
        elif color_mode == "grayscale":
            options['ColorModel'] = 'Gray'
        orientation = settings.get("orientation", "").lower()
        if orientation == "portrait":
            options['orientation-requested'] = '3'
        elif orientation == "landscape":
            options['orientation-requested'] = '4'
        paper_size = settings.get("paperSize", "")
        if paper_size:
            options['media'] = paper_size
        job_id = conn.printFile(printer_name, file_path, "PrinterSync Job", options)
        logging.info(f"Print job successful for {file_path} on {printer_name}, job ID: {job_id}")
        return True
    except Exception as e:
        logging.error(f"Error during printing: {e}")
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
    mac_version = "Unknown"
    try:
        mac_version = subprocess.check_output(["sw_vers", "-productVersion"]).decode().strip()
    except:
        pass
    return {
        "hostname": socket.gethostname(),
        "ip": socket.gethostbyname(socket.gethostname()),
        "public_ip": public_ip,
        "os": platform.system(),
        "os_version": mac_version or platform.version(),
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

# ------------------ Toga GUI Application ------------------
class PrinterApp(toga.App):
    def __init__(self):
        super().__init__('PrinterSync Pro', 'com.example.printersync')
        self.stop_event = threading.Event()
        self.update_queue = queue.Queue()
        self.printers = []
        self.jobs = {}
        self.user_id = None
        self.listener = None

    def startup(self):
        """Initialize the Toga application."""
        self.main_window = toga.MainWindow(title="self.name", size=(1100, 800))
        self.content_box = toga.Box(style=toga.style.Pack(direction=COLUMN))
        self.main_window.content = self.content_box
        self.show_token_input()
        self.main_window.show()
        self.check_update_queue()
        
        # Load token and connect if available
        token = load_token()
        if token:
            self.token_entry.value = token
            self.on_connect(None)

    def show_token_input(self):
        """Display the token input interface."""
        self.content_box.clear()
        
        # Header
        header_box = toga.Box(style=toga.style.Pack(direction=ROW, padding=10))
        title_label = toga.Label('PrinterSync Pro', style=toga.style.Pack(font_size=24))
        subtitle_label = toga.Label('macOS Edition', style=toga.style.Pack(font_size=16))
        header_box.add(title_label)
        header_box.add(subtitle_label)
        self.content_box.add(header_box)
        
        # Token input
        token_frame = toga.Box(style=toga.style.Pack(direction=COLUMN, padding=10))
        token_header = toga.Label('Connect Your Account', style=toga.style.Pack(font_size=18))
        token_description = toga.Label(
            'Enter your connection token to link this device with your account',
            style=toga.style.Pack(font_size=14)
        )
        self.token_entry = toga.TextInput(
            placeholder='Paste your token here',
            style=toga.style.Pack(flex=1)
        )
        submit_button = toga.Button(
            'Connect',
            on_press=self.on_connect,
            style=toga.style.Pack(width=150)
        )
        token_input_frame = toga.Box(style=toga.style.Pack(direction=ROW))
        token_input_frame.add(self.token_entry)
        token_input_frame.add(submit_button)
        token_frame.add(token_header)
        token_frame.add(token_description)
        token_frame.add(token_input_frame)
        self.content_box.add(token_frame)
        
        # Status
        status_box = toga.Box(style=toga.style.Pack(direction=ROW, padding=10))
        self.status_label = toga.Label('Disconnected', style=toga.style.Pack(color='red'))
        status_box.add(self.status_label)
        self.content_box.add(status_box)

    def show_connected_interface(self):
        """Display the connected interface with tabs."""
        self.content_box.clear()
        
        # Header
        header_box = toga.Box(style=toga.style.Pack(direction=ROW, padding=10))
        title_label = toga.Label('PrinterSync Pro', style=toga.style.Pack(font_size=24))
        subtitle_label = toga.Label('macOS Edition', style=toga.style.Pack(font_size=16))
        header_box.add(title_label)
        header_box.add(subtitle_label)
        self.content_box.add(header_box)
        
        # Status
        status_box = toga.Box(style=toga.style.Pack(direction=ROW, padding=10))
        self.status_label = toga.Label('Connected', style=toga.style.Pack(color='green'))
        status_box.add(self.status_label)
        self.content_box.add(status_box)
        
        # Tabs
        self.tabs = toga.Tab()
        self.printers_tab = toga.ScrollContainer(
            content=toga.Box(style=toga.style.Pack(direction=COLUMN))
        )
        self.jobs_tab = toga.ScrollContainer(
            content=toga.Box(style=toga.style.Pack(direction=COLUMN))
        )
        self.logs_tab = toga.ScrollContainer(
            content=toga.Box(style=toga.style.Pack(direction=COLUMN))
        )
        self.log_textbox = toga.MultilineTextInput(
            readonly=True,
            style=toga.style.Pack(flex=1)
        )
        self.logs_tab.content.add(self.log_textbox)
        self.tabs.add('Printers', self.printers_tab)
        self.tabs.add('Jobs', self.jobs_tab)
        self.tabs.add('Logs', self.logs_tab)
        self.content_box.add(self.tabs)
        
        # Populate printers
        self.refresh_printers()

    def on_connect(self, widget):
        """Handle connection button press."""
        token = self.token_entry.value.strip()
        if not token:
            self.main_window.info_dialog('Error', 'Please enter a valid token!')
            return
        self.add_background_task(lambda: self.connect_to_printer(token))

    def connect_to_printer(self, token):
        """Connect to Firebase and start processing jobs."""
        try:
            if not firebase_admin._apps:
                init_firebase()
            users_ref = db.reference("users")
            user_snapshot = users_ref.order_by_child("token").equal_to(token).get()
            if not user_snapshot:
                self.main_window.invoke(lambda: self.main_window.info_dialog('Error', 'Invalid token!'))
                return
            user_info = next(iter(user_snapshot.values()))
            self.user_id = token
            update_connection_status(self.user_id, True)
            self.main_window.invoke(lambda: self.status_label.set_text('Connected'))
            self.main_window.invoke(lambda: self.status_label.style.update(color='green'))
            self.main_window.invoke(lambda: self.show_connected_interface())
            save_token(token)
            upload_system_info(self.user_id)
            self.main_window.invoke(lambda: self.refresh_printers())
            self.start_job_listener()
            self.update_queue.put({'type': 'log', 'message': f"Connected successfully with token: {token}"})
        except Exception as e:
            self.update_queue.put({'type': 'log', 'message': f"Connection error: {e}"})
            self.main_window.invoke(lambda: self.main_window.info_dialog('Error', f"Connection failed: {e}"))

    def refresh_printers(self):
        """Update the list of available printers."""
        try:
            self.printers_tab.content.children = []
            self.printers = update_printer_list(self.user_id)
            if not self.printers:
                no_printers_label = toga.Label(
                    'No printers found. Please check your printer connections.',
                    style=toga.style.Pack(padding=10)
                )
                self.printers_tab.content.add(no_printers_label)
            else:
                for printer in self.printers:
                    printer_box = toga.Box(style=toga.style.Pack(direction=ROW, padding=5))
                    icon_label = toga.Label('🖨️', style=toga.style.Pack(padding=5))
                    name_label = toga.Label(printer, style=toga.style.Pack(flex=1, padding=5))
                    status_label = toga.Label('Ready', style=toga.style.Pack(color='green', padding=5))
                    select_button = toga.Button(
                        'Select',
                        on_press=lambda widget, p=printer: self.select_printer(p),
                        style=toga.style.Pack(width=100)
                    )
                    printer_box.add(icon_label)
                    printer_box.add(name_label)
                    printer_box.add(status_label)
                    printer_box.add(select_button)
                    self.printers_tab.content.add(printer_box)
            self.update_queue.put({'type': 'log', 'message': f"Found {len(self.printers)} printers"})
        except Exception as e:
            self.update_queue.put({'type': 'log', 'message': f"Error refreshing printers: {e}"})

    def select_printer(self, printer):
        """Set the selected printer as default."""
        try:
            self.update_queue.put({'type': 'log', 'message': f"Selected printer: {printer}"})
            self.main_window.info_dialog('Printer Selected', f"Selected printer: {printer}")
        except Exception as e:
            self.update_queue.put({'type': 'log', 'message': f"Error selecting printer: {e}"})

    def start_job_listener(self):
        """Start listening for print jobs from Firebase."""
        def listener_task():
            try:
                if self.listener:
                    self.listener.close()
                users_ref = db.reference("users")
                user_snapshot = users_ref.order_by_child("token").equal_to(self.user_id).get()
                user_info = next(iter(user_snapshot.values()))
                user = user_info['id']
                jobs_ref = db.reference(f"users/{user}/jobs")
                
                def on_job_added(event):
                    if event.event_type == 'put' and event.path != '/' and event.data:
                        job_key = event.path.lstrip('/')
                        job_data = event.data
                        if isinstance(job_data, dict) and job_data.get('status') == 'pending':
                            self.main_window.invoke(lambda: self.process_job(user, job_key, job_data))
                
                self.listener = jobs_ref.listen(on_job_added)
                self.update_queue.put({'type': 'log', 'message': "Started listening for print jobs"})
            except Exception as e:
                self.update_queue.put({'type': 'log', 'message': f"Error starting job listener: {e}"})
        
        threading.Thread(target=listener_task, daemon=True).start()

    def process_job(self, user, job_key, job_data):
        """Process a print job."""
        try:
            self.tabs.select_index(1)  # Switch to Jobs tab
            job_box = toga.Box(style=toga.style.Pack(direction=COLUMN, padding=5))
            job_header = toga.Box(style=toga.style.Pack(direction=ROW))
            job_title = toga.Label(f"Job: {job_key}", style=toga.style.Pack(flex=1))
            job_time = toga.Label(time.strftime("%H:%M:%S"))
            job_header.add(job_title)
            job_header.add(job_time)
            progress_frame = toga.Box(style=toga.style.Pack(direction=ROW))
            progress_bar = toga.ProgressBar(max=1.0, value=0)
            status_label = toga.Label('Downloading...', style=toga.style.Pack(color='orange'))
            progress_frame.add(progress_bar)
            progress_frame.add(status_label)
            job_details = toga.Box(style=toga.style.Pack(direction=ROW))
            printer_info = toga.Label(f"Printer: {job_data.get('printer', 'Default')}")
            settings_info = toga.Label(f"Settings: {job_data.get('colorMode', 'Color')}, {job_data.get('paperSize', 'A4')}")
            job_details.add(printer_info)
            job_details.add(settings_info)
            job_box.add(job_header)
            job_box.add(progress_frame)
            job_box.add(job_details)
            self.jobs_tab.content.add(job_box)
            db.reference(f"users/{user}/jobs/{job_key}").update({"status": "processing"})
            self.add_background_task(
                lambda: self.download_and_print(user, job_key, job_data, progress_bar, status_label)
            )
            self.update_queue.put({'type': 'log', 'message': f"Processing job: {job_key}"})
        except Exception as e:
            self.update_queue.put({'type': 'log', 'message': f"Error processing job: {e}"})
            db.reference(f"users/{user}/jobs/{job_key}").update({"status": "error", "error": str(e)})

    def download_and_print(self, user, job_key, job_data, progress_bar, status_label):
        """Download and print a file."""
        try:
            file_url = job_data.get('fileUrl')
            self.main_window.invoke(lambda: status_label.set_text('Downloading...'))
            def progress_callback(progress):
                self.main_window.invoke(lambda: progress_bar.set_value(progress))
            local_file = download_pdf_from_url(file_url, job_key, progress_callback)
            self.main_window.invoke(lambda: status_label.set_text('Printing...'))
            printer_settings = {
                "namePrinter": job_data.get('printer', ''),
                "colorMode": job_data.get('colorMode', 'color'),
                "orientation": job_data.get('orientation', 'portrait'),
                "paperSize": job_data.get('paperSize', 'A4')
            }
            success = print_pdf(printer_settings, local_file)
            if success:
                self.main_window.invoke(lambda: status_label.set_text('Completed'))
                self.main_window.invoke(lambda: status_label.style.update(color='green'))
                db.reference(f"users/{user}/jobs/{job_key}").update({"status": "completed"})
            else:
                self.main_window.invoke(lambda: status_label.set_text('Failed'))
                self.main_window.invoke(lambda: status_label.style.update(color='red'))
                db.reference(f"users/{user}/jobs/{job_key}").update({
                    "status": "error",
                    "error": "Printing failed"
                })
            self.update_queue.put({'type': 'log', 'message': f"Job {job_key} {'completed' if success else 'failed'}"})
        except Exception as e:
            self.main_window.invoke(lambda: status_label.set_text('Error'))
            self.main_window.invoke(lambda: status_label.style.update(color='red'))
            self.update_queue.put({'type': 'log', 'message': f"Error in job {job_key}: {e}"})
            db.reference(f"users/{user}/jobs/{job_key}").update({"status": "error", "error": str(e)})

    def check_update_queue(self):
        """Update UI based on queued messages."""
        while not self.update_queue.empty():
            message = self.update_queue.get()
            if message['type'] == 'log':
                self.log_textbox.value += message['message'] + '\n'
        self.app.loop.call_later(0.1, self.check_update_queue)

    def shutdown(self):
        """Handle application shutdown."""
        try:
            if self.user_id:
                update_connection_status(self.user_id, False)
            if self.listener:
                self.listener.close()
            self.stop_event.set()
        except Exception as e:
            logging.error(f"Error shutting down app: {e}")

if __name__ == "__main__":
    try:
        init_firebase()
        app = PrinterApp()
        app.main_loop()
    except Exception as e:
        logging.error(f"Application error: {e}")
        # Toga doesn't have a built-in messagebox like tkinter, so log the error
