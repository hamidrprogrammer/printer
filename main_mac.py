import time
import uuid
import json
import requests
import cups  # Replace win32print with cups for macOS
import firebase_admin
from firebase_admin import credentials, db
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import scrolledtext
import threading
import queue
import socket
import platform
import logging
from concurrent.futures import ThreadPoolExecutor
import subprocess
from PIL import Image
import sys
import tempfile
import os

# Configure logging for detailed event tracking
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
    """Retrieve list of installed printers (local and network)."""
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
        headers = {
            "Accept": "application/pdf",
        }
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
    
    # If no printer specified, use default
    if not printer_name:
        conn = cups.Connection()
        printers = conn.getPrinters()
        if printers:
            printer_name = list(printers.keys())[0]
        else:
            logging.error("No printers available")
            return False
    
    try:
        # Create a CUPS connection
        conn = cups.Connection()
        
        # Set options based on settings
        options = {}
        
        # Map color mode
        color_mode = settings.get("colorMode", "")
        if color_mode.lower() == "color":
            options['ColorModel'] = 'RGB'
        elif color_mode.lower() == "grayscale":
            options['ColorModel'] = 'Gray'
        
        # Map orientation
        orientation = settings.get("orientation", "")
        if orientation.lower() == "portrait":
            options['orientation-requested'] = '3'  # Portrait
        elif orientation.lower() == "landscape":
            options['orientation-requested'] = '4'  # Landscape
        
        # Map paper size
        paper_size = settings.get("paperSize", "")
        if paper_size:
            options['media'] = paper_size
        
        # Print the PDF
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
    
    # Get macOS specific information
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

# ------------------ macOS Menu Bar Management ------------------
# Placeholder implementation using Tkinter (replace with rumps for production)
def create_menu_bar_app(app):
    """Create a menu bar app for macOS."""
    def on_show():
        app.deiconify()
        app.lift()

    def on_exit():
        app.quit_app()
    
    # Simple Tkinter menu window
    menu_window = tk.Toplevel(app)
    menu_window.title("PrinterSync Menu")
    menu_window.geometry("200x100")
    
    show_button = tk.Button(menu_window, text="Show App", command=on_show, bg="#2196F3", fg="#FFFFFF", font=("SF Pro Text", 14))
    show_button.pack(pady=10)
    
    exit_button = tk.Button(menu_window, text="Exit", command=on_exit, bg="#F44336", fg="#FFFFFF", font=("SF Pro Text", 14))
    exit_button.pack(pady=10)
    
    # Hide the menu window initially
    menu_window.withdraw()
    
    return menu_window

# ------------------ Helper Function for Scrollable Frame ------------------
def create_scrollable_frame(parent, bg="#FFFFFF"):
    """Create a scrollable frame using Canvas and Scrollbar."""
    canvas = tk.Canvas(parent, bg=bg)
    scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg=bg)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    
    return scrollable_frame

# ------------------ GUI Application ------------------
class PrinterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.stop_event = threading.Event()
        self.update_queue = queue.Queue()
        self.printers = []
        self.jobs = {}
        self.user_id = None
        self.menu_bar = None
        self.listener = None

        # Window setup
        self.title("PrinterSync Pro")
        self.geometry("1100x800")
        self.minsize(900, 650)
        
        # Define custom colors
        self.primary_color = "#2196F3"  # Material Blue
        self.success_color = "#4CAF50"  # Material Green
        self.warning_color = "#FFC107"  # Material Amber
        self.error_color = "#F44336"    # Material Red
        self.bg_color = "#F5F5F5"       # Light background
        self.card_color = "#FFFFFF"     # Card background
        self.text_color = "#212121"     # Primary text
        self.secondary_text = "#757575" # Secondary text

        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Header
        self.header_frame = tk.Frame(self, bg="#1976D2")
        self.header_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        
        self.header_content = tk.Frame(self.header_frame, bg="#1976D2")
        self.header_content.pack(pady=15, padx=20, fill="x")
        
        self.title_label = tk.Label(
            self.header_content,
            text="PrinterSync Pro",
            font=("SF Pro Display", 32, "bold"),
            bg="#1976D2",
            fg="#FFFFFF"
        )
        self.title_label.pack(side="left", padx=10)
        
        self.subtitle_label = tk.Label(
            self.header_content,
            text="macOS Edition",
            font=("SF Pro Text", 16),
            bg="#1976D2",
            fg="#E1F5FE"
        )
        self.subtitle_label.pack(side="left", padx=10)

        # Token input
        self.token_frame = tk.Frame(self, bg=self.card_color)
        self.token_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        self.token_header = tk.Label(
            self.token_frame,
            text="Connect Your Account",
            font=("SF Pro Display", 18, "bold"),
            bg=self.card_color,
            fg=self.text_color
        )
        self.token_header.pack(pady=(15, 5), padx=20, anchor="w")
        
        self.token_description = tk.Label(
            self.token_frame,
            text="Enter your connection token to link this device with your account",
            font=("SF Pro Text", 14),
            bg=self.card_color,
            fg=self.secondary_text
        )
        self.token_description.pack(pady=(0, 15), padx=20, anchor="w")
        
        self.token_input_frame = tk.Frame(self.token_frame, bg=self.card_color)
        self.token_input_frame.pack(pady=5, padx=20, fill="x")
        
        self.token_entry = tk.Entry(
            self.token_input_frame,
            width=40,
            font=("SF Pro Text", 14),
            borderwidth=1
        )
        self.token_entry.pack(side="left", pady=10, fill="x", expand=True)
        
        self.submit_button = tk.Button(
            self.token_input_frame,
            text="Connect",
            command=self.on_connect,
            width=15,
            font=("SF Pro Text", 14, "bold"),
            bg=self.primary_color,
            fg="#FFFFFF"
        )
        self.submit_button.pack(side="right", pady=10, padx=(15, 0))

        # Connection status
        self.status_frame = tk.Frame(self, bg=self.card_color)
        self.status_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        self.status_indicator = tk.Frame(self.status_frame, width=12, height=12, bg=self.error_color)
        self.status_indicator.pack(side="left", padx=(15, 5), pady=10)
        
        self.status_label = tk.Label(
            self.status_frame,
            text="Disconnected",
            font=("SF Pro Text", 14),
            bg=self.card_color,
            fg=self.text_color
        )
        self.status_label.pack(side="left", pady=10)

        # Main content area
        self.main_frame = tk.Frame(self, bg=self.card_color)
        self.main_frame.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_remove()
        
        # Tab navigation
        self.tab_frame = tk.Frame(self.main_frame, bg=self.card_color)
        self.tab_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        self.tab_buttons = []
        tab_data = [
            {"name": "Printers", "icon": "🖨️"},
            {"name": "Jobs", "icon": "📋"},
            {"name": "Logs", "icon": "📊"}
        ]
        
        for i, tab in enumerate(tab_data):
            bg_color = self.primary_color if i == 0 else self.card_color
            fg_color = "#FFFFFF" if i == 0 else self.text_color
            tab_button = tk.Button(
                self.tab_frame,
                text=f"{tab['icon']} {tab['name']}",
                font=("SF Pro Text", 14),
                bg=bg_color,
                fg=fg_color,
                width=12,
                command=lambda idx=i: self.switch_tab(idx)
            )
            tab_button.pack(side="left", padx=(0 if i > 0 else 0, 10))
            self.tab_buttons.append(tab_button)
        
        # Content frames for each tab
        self.content_frames = []
        
        # Printers tab
        self.printers_content = tk.Frame(self.main_frame, bg=self.card_color)
        self.printers_content.grid(row=1, column=0, sticky="nsew")
        self.content_frames.append(self.printers_content)
        
        self.printers_header = tk.Frame(self.printers_content, bg=self.card_color)
        self.printers_header.pack(fill="x", padx=20, pady=15)
        
        self.printers_title = tk.Label(
            self.printers_header,
            text="Available Printers",
            font=("SF Pro Display", 20, "bold"),
            bg=self.card_color,
            fg=self.text_color
        )
        self.printers_title.pack(side="left")
        
        self.refresh_button = tk.Button(
            self.printers_header,
            text="Refresh",
            command=self.refresh_printers,
            bg=self.primary_color,
            fg="#FFFFFF",
            width=12,
            font=("SF Pro Text", 14)
        )
        self.refresh_button.pack(side="right")
        
        self.printers_list_frame = tk.Frame(self.printers_content, bg=self.card_color)
        self.printers_list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.printers_list = create_scrollable_frame(self.printers_list_frame)
        
        # Jobs tab
        self.jobs_content = tk.Frame(self.main_frame, bg=self.card_color)
        self.jobs_content.grid(row=1, column=0, sticky="nsew")
        self.jobs_content.grid_remove()
        self.content_frames.append(self.jobs_content)
        
        self.jobs_header = tk.Frame(self.jobs_content, bg=self.card_color)
        self.jobs_header.pack(fill="x", padx=20, pady=15)
        
        self.jobs_title = tk.Label(
            self.jobs_header,
            text="Print Jobs",
            font=("SF Pro Display", 20, "bold"),
            bg=self.card_color,
            fg=self.text_color
        )
        self.jobs_title.pack(side="left")
        
        self.jobs_list_frame = tk.Frame(self.jobs_content, bg=self.card_color)
        self.jobs_list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.jobs_table = create_scrollable_frame(self.jobs_list_frame)
        
        # Logs tab
        self.logs_content = tk.Frame(self.main_frame, bg=self.card_color)
        self.logs_content.grid(row=1, column=0, sticky="nsew")
        self.logs_content.grid_remove()
        self.content_frames.append(self.logs_content)
        
        self.logs_header = tk.Frame(self.logs_content, bg=self.card_color)
        self.logs_header.pack(fill="x", padx=20, pady=15)
        
        self.logs_title = tk.Label(
            self.logs_header,
            text="Event Logs",
            font=("SF Pro Display", 20, "bold"),
            bg=self.card_color,
            fg=self.text_color
        )
        self.logs_title.pack(side="left")
        
        self.clear_logs_button = tk.Button(
            self.logs_header,
            text="Clear Logs",
            bg="#E0E0E0",
            fg=self.text_color,
            width=12,
            font=("SF Pro Text", 14),
            command=self.clear_logs
        )
        self.clear_logs_button.pack(side="right")
        
        self.logs_frame = tk.Frame(self.logs_content, bg=self.card_color)
        self.logs_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.log_textbox = scrolledtext.ScrolledText(
            self.logs_frame,
            font=("SF Pro Mono", 12),
            bg="#FAFAFA",
            fg="#000000",
            height=20
        )
        self.log_textbox.pack(fill="both", expand=True)

        # Menu bar setup
        self.menu_bar = create_menu_bar_app(self)

        # Event handlers
        self.protocol("WM_DELETE_WINDOW", self.on_minimize)
        self.after(100, self.check_update_queue)

        # Load token
        token = load_token()
        if token:
            self.token_entry.insert(0, token)
            self.on_connect()

    def switch_tab(self, tab_index):
        """Switch between tabs."""
        for i, frame in enumerate(self.content_frames):
            if i == tab_index:
                frame.grid()
            else:
                frame.grid_remove()
                
        for i, button in enumerate(self.tab_buttons):
            if i == tab_index:
                button.configure(bg=self.primary_color, fg="#FFFFFF")
            else:
                button.configure(bg=self.card_color, fg=self.text_color)

    def clear_logs(self):
        """Clear the log textbox."""
        self.log_textbox.delete("1.0", "end")
        self.update_queue.put({'type': 'log', 'message': "Logs cleared"})

    def check_update_queue(self):
        """Update UI based on queued messages."""
        while not self.update_queue.empty():
            message = self.update_queue.get()
            if message['type'] == 'log':
                self.log_textbox.insert("end", message['message'] + "\n")
                self.log_textbox.see("end")
            elif message['type'] == 'progress':
                progress_var = message['progress_var']
                try:
                    progress_var.set(message['value'] * 100)  # Scale 0-1 to 0-100
                except Exception as e:
                    print(f"Error updating progress bar: {e}")
        self.after(100, self.check_update_queue)

    def on_connect(self):
        """Validate token and initiate connection."""
        token = self.token_entry.get().strip()
        if not token:
            messagebox.showerror("Error", "Please enter a valid token!")
            return
        threading.Thread(target=self.connect_to_printer, args=(token,), daemon=True).start()

    def connect_to_printer(self, token):
        """Connect to Firebase and start processing jobs."""
        try:
            if not firebase_admin._apps:
                init_firebase()
                
            users_ref = db.reference("users")
            user_snapshot = users_ref.order_by_child("token").equal_to(token).get()
            if not user_snapshot:
                self.after(0, lambda: messagebox.showerror("Error", "Invalid token!"))
                return
            user_info = next(iter(user_snapshot.values()))
            self.user_id = token
            update_connection_status(self.user_id, True)
            
            # Update UI
            self.after(0, lambda: self.status_indicator.configure(bg=self.success_color))
            self.after(0, lambda: self.status_label.configure(text="Connected"))
            self.after(0, lambda: self.main_frame.grid())
            
            save_token(token)
            upload_system_info(self.user_id)
            self.refresh_printers()
            self.start_job_listener()
            
            self.update_queue.put({'type': 'log', 'message': f"Connected successfully with token: {token}"})
        except Exception as e:
            self.update_queue.put({'type': 'log', 'message': f"Connection error: {e}"})
            self.after(0, lambda: messagebox.showerror("Error", f"Connection failed: {e}"))

    def refresh_printers(self):
        """Update the list of available printers."""
        try:
            for widget in self.printers_list.winfo_children():
                widget.destroy()
            
            self.printers = update_printer_list(self.user_id)
            
            if not self.printers:
                no_printers_label = tk.Label(
                    self.printers_list,
                    text="No printers found. Please check your printer connections.",
                    font=("SF Pro Text", 14),
                    bg=self.card_color,
                    fg=self.secondary_text
                )
                no_printers_label.pack(pady=20)
            
            for i, printer in enumerate(self.printers):
                printer_card = tk.Frame(
                    self.printers_list,
                    bg="#F9F9F9",
                    borderwidth=1,
                    relief="solid"
                )
                printer_card.pack(fill="x", padx=5, pady=5)
                
                printer_icon = tk.Label(
                    printer_card,
                    text="🖨️",
                    font=("SF Pro Text", 20),
                    bg="#F9F9F9"
                )
                printer_icon.pack(side="left", padx=(15, 10), pady=15)
                
                printer_info = tk.Frame(printer_card, bg="#F9F9F9")
                printer_info.pack(side="left", fill="both", expand=True, pady=10)
                
                printer_name = tk.Label(
                    printer_info,
                    text=printer,
                    font=("SF Pro Text", 14, "bold"),
                    bg="#F9F9F9",
                    fg=self.text_color,
                    anchor="w"
                )
                printer_name.pack(anchor="w")
                
                printer_status = tk.Label(
                    printer_info,
                    text="Ready",
                    font=("SF Pro Text", 12),
                    bg="#F9F9F9",
                    fg=self.success_color,
                    anchor="w"
                )
                printer_status.pack(anchor="w")
                
                select_button = tk.Button(
                    printer_card,
                    text="Select",
                    width=10,
                    font=("SF Pro Text", 13),
                    bg=self.primary_color,
                    fg="#FFFFFF",
                    command=lambda p=printer: self.select_printer(p)
                )
                select_button.pack(side="right", padx=15)
            
            self.update_queue.put({'type': 'log', 'message': f"Found {len(self.printers)} printers"})
        except Exception as e:
            self.update_queue.put({'type': 'log', 'message': f"Error refreshing printers: {e}"})

    def select_printer(self, printer):
        """Set the selected printer as default."""
        try:
            self.update_queue.put({'type': 'log', 'message': f"Selected printer: {printer}"})
            messagebox.showinfo("Printer Selected", f"Selected printer: {printer}")
        except Exception as e:
            self.update_queue.put({'type': 'log', 'message': f"Error selecting printer: {e}"})

    def start_job_listener(self):
        """Start listening for print jobs from Firebase."""
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
                        self.process_job(user, job_key, job_data)
            
            self.listener = jobs_ref.listen(on_job_added)
            self.update_queue.put({'type': 'log', 'message': "Started listening for print jobs"})
        except Exception as e:
            self.update_queue.put({'type': 'log', 'message': f"Error starting job listener: {e}"})

    def process_job(self, user, job_key, job_data):
        """Process a print job."""
        try:
            self.after(0, lambda: self.switch_tab(1))
            
            job_card = tk.Frame(
                self.jobs_table,
                bg="#F9F9F9",
                borderwidth=1,
                relief="solid"
            )
            job_card.pack(fill="x", padx=5, pady=5)
            
            job_header = tk.Frame(job_card, bg="#F9F9F9")
            job_header.pack(fill="x", padx=15, pady=(15, 5))
            
            job_title = tk.Label(
                job_header,
                text=f"Job: {job_key}",
                font=("SF Pro Text", 14, "bold"),
                bg="#F9F9F9",
                fg=self.text_color
            )
            job_title.pack(side="left")
            
            job_time = tk.Label(
                job_header,
                text=time.strftime("%H:%M:%S"),
                font=("SF Pro Text", 12),
                bg="#F9F9F9",
                fg=self.secondary_text
            )
            job_time.pack(side="right")
            
            job_content = tk.Frame(job_card, bg="#F9F9F9")
            job_content.pack(fill="x", padx=15, pady=5)
            
            progress_frame = tk.Frame(job_content, bg="#F9F9F9")
            progress_frame.pack(fill="x", pady=5)
            
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(
                progress_frame,
                orient="horizontal",
                length=400,
                mode="determinate",
                variable=progress_var
            )
            progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))
            
            status_label = tk.Label(
                progress_frame,
                text="Downloading...",
                font=("SF Pro Text", 12),
                width=10,
                bg="#F9F9F9",
                fg=self.warning_color
            )
            status_label.pack(side="right")
            
            job_details = tk.Frame(job_card, bg="#F9F9F9")
            job_details.pack(fill="x", padx=15, pady=(5, 15))
            
            printer_info = tk.Label(
                job_details,
                text=f"Printer: {job_data.get('printer', 'Default')}",
                font=("SF Pro Text", 12),
                bg="#F9F9F9",
                fg=self.secondary_text
            )
            printer_info.pack(side="left")
            
            settings_info = tk.Label(
                job_details,
                text=f"Settings: {job_data.get('colorMode', 'Color')}, {job_data.get('paperSize', 'A4')}",
                font=("SF Pro Text", 12),
                bg="#F9F9F9",
                fg=self.secondary_text
            )
            settings_info.pack(side="right")
            
            db.reference(f"users/{user}/jobs/{job_key}").update({"status": "processing"})
            
            def update_progress(progress):
                self.update_queue.put({'type': 'progress', 'progress_var': progress_var, 'value': progress})
            
            file_url = job_data.get('fileUrl')
            
            threading.Thread(
                target=self.download_and_print,
                args=(user, job_key, job_data, update_progress, status_label),
                daemon=True
            ).start()
            
            self.update_queue.put({'type': 'log', 'message': f"Processing job: {job_key}"})
        except Exception as e:
            self.update_queue.put({'type': 'log', 'message': f"Error processing job: {e}"})
            db.reference(f"users/{user}/jobs/{job_key}").update({
                "status": "error",
                "error": str(e)
            })

    def download_and_print(self, user, job_key, job_data, progress_callback, status_label):
        """Download and print a file."""
        try:
            file_url = job_data.get('fileUrl')
            
            self.after(0, lambda: status_label.configure(text="Downloading...", fg=self.warning_color))
            
            local_file = download_pdf_from_url(file_url, job_key, progress_callback)
            
            self.after(0, lambda: status_label.configure(text="Printing...", fg=self.warning_color))
            
            printer_settings = {
                "namePrinter": job_data.get('printer', ''),
                "colorMode": job_data.get('colorMode', 'color'),
                "orientation": job_data.get('orientation', 'portrait'),
                "paperSize": job_data.get('paperSize', 'A4')
            }
            
            success = print_pdf(printer_settings, local_file)
            
            if success:
                self.after(0, lambda: status_label.configure(text="Completed", fg=self.success_color))
                db.reference(f"users/{user}/jobs/{job_key}").update({"status": "completed"})
            else:
                self.after(0, lambda: status_label.configure(text="Failed", fg=self.error_color))
                db.reference(f"users/{user}/jobs/{job_key}").update({
                    "status": "error",
                    "error": "Printing failed"
                })
            
            self.update_queue.put({'type': 'log', 'message': f"Job {job_key} {'completed' if success else 'failed'}"})
        except Exception as e:
            self.after(0, lambda: status_label.configure(text="Error", fg=self.error_color))
            self.update_queue.put({'type': 'log', 'message': f"Error in job {job_key}: {e}"})
            db.reference(f"users/{user}/jobs/{job_key}").update({
                "status": "error",
                "error": str(e)
            })

    def on_minimize(self):
        """Minimize to menu bar instead of closing."""
        self.withdraw()
        self.update_queue.put({'type': 'log', 'message': "Application minimized to menu bar"})

    def quit_app(self):
        """Properly quit the application."""
        try:
            if self.user_id:
                update_connection_status(self.user_id, False)
            
            if self.listener:
                self.listener.close()
            
            self.stop_event.set()
            self.destroy()
        except Exception as e:
            print(f"Error quitting app: {e}")
            self.destroy()

if __name__ == "__main__":
    try:
        init_firebase()
        app = PrinterApp()
        app.mainloop()
    except Exception as e:
        logging.error(f"Application error: {e}")
        messagebox.showerror("Error", f"Application error: {e}")
