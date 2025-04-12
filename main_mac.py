import os
import time
import uuid
import json
import requests
import cups  # Using cups for macOS printer management
import firebase_admin
from firebase_admin import credentials, db
import customtkinter as ctk
from tkinter import messagebox
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

# Set environment variable to silence Tk deprecation warning on macOS
os.environ["TK_SILENCE_DEPRECATION"] = "1"

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
        conn = cups.Connection()
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
    except Exception as e:
        logging.error(f"Error retrieving macOS version: {e}")
    
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
def create_menu_bar_app(app):
    """Create a menu bar app for macOS."""
    def on_show():
        app.deiconify()
        app.lift()

    def on_exit():
        app.quit_app()
    
    # For debugging, we use a toplevel window with a distinct background color
    menu_window = ctk.CTkToplevel(app)
    menu_window.title("PrinterSync Menu")
    menu_window.geometry("200x100")
    menu_window.configure(fg_color="#DDDDDD")  # Debug color
    
    show_button = ctk.CTkButton(menu_window, text="Show App", command=on_show)
    show_button.pack(pady=10)
    
    exit_button = ctk.CTkButton(menu_window, text="Exit", command=on_exit)
    exit_button.pack(pady=10)
    
    # Hide the menu window initially
    menu_window.withdraw()
    
    return menu_window

# ------------------ GUI Application ------------------
class PrinterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.stop_event = threading.Event()
        self.update_queue = queue.Queue()
        self.printers = []
        self.jobs = {}
        self.user_id = None
        self.menu_bar = None
        self.listener = None

        # Window setup - try a modern macOS style appearance
        self.title("PrinterSync Pro")
        self.geometry("1100x800")
        ctk.set_appearance_mode("dark")  # Try dark mode; experiment with "light" if needed
        ctk.set_default_color_theme("blue")
        self.minsize(900, 650)
        
        # Custom color definitions
        self.primary_color = "#2196F3"  # Material Blue
        self.success_color = "#4CAF50"  # Material Green
        self.warning_color = "#FFC107"  # Material Amber
        self.error_color = "#F44336"    # Material Red
        self.bg_color = "#F5F5F5"       # Light background
        self.card_color = "#FFFFFF"     # Card background
        self.text_color = "#212121"     # Primary text
        self.secondary_text = "#757575" # Secondary text

        # Configure grid behavior
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # ---------------- Header Section ----------------
        self.header_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#1976D2")
        self.header_frame.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        
        self.header_content = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.header_content.pack(pady=15, padx=20, fill="x")
        
        self.title_label = ctk.CTkLabel(
            self.header_content,
            text="PrinterSync Pro",
            font=("SF Pro Display", 32, "bold"),
            text_color="#FFFFFF"
        )
        self.title_label.pack(side="left", padx=10)
        
        self.subtitle_label = ctk.CTkLabel(
            self.header_content,
            text="macOS Edition",
            font=("SF Pro Text", 16),
            text_color="#E1F5FE"
        )
        self.subtitle_label.pack(side="left", padx=10)

        # ---------------- Token Input Section ----------------
        self.token_frame = ctk.CTkFrame(self, corner_radius=15, fg_color=self.card_color)
        self.token_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        
        self.token_header = ctk.CTkLabel(
            self.token_frame,
            text="Connect Your Account",
            font=("SF Pro Display", 18, "bold"),
            text_color=self.text_color
        )
        self.token_header.pack(pady=(15, 5), padx=20, anchor="w")
        
        self.token_description = ctk.CTkLabel(
            self.token_frame,
            text="Enter your connection token to link this device with your account",
            font=("SF Pro Text", 14),
            text_color=self.secondary_text
        )
        self.token_description.pack(pady=(0, 15), padx=20, anchor="w")
        
        self.token_input_frame = ctk.CTkFrame(self.token_frame, fg_color="transparent")
        self.token_input_frame.pack(pady=5, padx=20, fill="x")
        
        self.token_entry = ctk.CTkEntry(
            self.token_input_frame,
            width=600,
            placeholder_text="Paste your token here",
            font=("SF Pro Text", 14),
            corner_radius=10,
            height=40,
            border_width=1
        )
        self.token_entry.pack(side="left", pady=10, fill="x", expand=True)
        
        self.submit_button = ctk.CTkButton(
            self.token_input_frame,
            text="Connect",
            command=self.on_connect,
            width=150,
            height=40,
            corner_radius=10,
            fg_color=self.primary_color,
            hover_color="#1565C0",
            font=("SF Pro Text", 14, "bold")
        )
        self.submit_button.pack(side="right", pady=10, padx=(15, 0))

        # ---------------- Connection Status Section ----------------
        self.status_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=self.card_color)
        self.status_frame.grid(row=2, column=0, padx=20, pady=5, sticky="ew")
        
        self.status_indicator = ctk.CTkFrame(self.status_frame, width=12, height=12, corner_radius=6, fg_color="#F44336")
        self.status_indicator.pack(side="left", padx=(15, 5), pady=10)
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="Disconnected",
            font=("SF Pro Text", 14),
            text_color=self.text_color
        )
        self.status_label.pack(side="left", pady=10)

        # ---------------- Main Content Area ----------------
        self.main_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="transparent")
        self.main_frame.grid(row=3, column=0, padx=20, pady=10, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_remove()
        
        # Tab Navigation
        self.tab_frame = ctk.CTkFrame(self.main_frame, corner_radius=0, fg_color="transparent")
        self.tab_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        self.tab_buttons = []
        tab_data = [
            {"name": "Printers", "icon": "🖨️"},
            {"name": "Jobs", "icon": "📋"},
            {"name": "Logs", "icon": "📊"}
        ]
        
        for i, tab in enumerate(tab_data):
            tab_button = ctk.CTkButton(
                self.tab_frame,
                text=f"{tab['icon']} {tab['name']}",
                font=("SF Pro Text", 14),
                fg_color="transparent" if i > 0 else self.primary_color,
                text_color=self.text_color if i > 0 else "#FFFFFF",
                hover_color="#E3F2FD",
                corner_radius=10,
                width=120,
                height=35,
                command=lambda idx=i: self.switch_tab(idx)
            )
            tab_button.pack(side="left", padx=(0 if i == 0 else 10))
            self.tab_buttons.append(tab_button)
        
        # ---------------- Content Frames for Tabs ----------------
        self.content_frames = []
        
        # Printers Tab
        self.printers_content = ctk.CTkFrame(self.main_frame, corner_radius=15, fg_color=self.card_color)
        self.printers_content.grid(row=1, column=0, sticky="nsew")
        self.content_frames.append(self.printers_content)
        
        self.printers_header = ctk.CTkFrame(self.printers_content, fg_color="transparent")
        self.printers_header.pack(fill="x", padx=20, pady=15)
        
        self.printers_title = ctk.CTkLabel(
            self.printers_header,
            text="Available Printers",
            font=("SF Pro Display", 20, "bold"),
            text_color=self.text_color
        )
        self.printers_title.pack(side="left")
        
        self.refresh_button = ctk.CTkButton(
            self.printers_header,
            text="Refresh",
            command=self.refresh_printers,
            corner_radius=10,
            fg_color=self.primary_color,
            hover_color="#1565C0",
            width=120,
            height=35,
            font=("SF Pro Text", 14)
        )
        self.refresh_button.pack(side="right")
        
        self.printers_list_frame = ctk.CTkFrame(self.printers_content, fg_color="transparent")
        self.printers_list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.printers_list = ctk.CTkScrollableFrame(
            self.printers_list_frame, 
            fg_color="transparent",
            corner_radius=0
        )
        self.printers_list.pack(fill="both", expand=True)
        
        # Jobs Tab
        self.jobs_content = ctk.CTkFrame(self.main_frame, corner_radius=15, fg_color=self.card_color)
        self.jobs_content.grid(row=1, column=0, sticky="nsew")
        self.jobs_content.grid_remove()
        self.content_frames.append(self.jobs_content)
        
        self.jobs_header = ctk.CTkFrame(self.jobs_content, fg_color="transparent")
        self.jobs_header.pack(fill="x", padx=20, pady=15)
        
        self.jobs_title = ctk.CTkLabel(
            self.jobs_header,
            text="Print Jobs",
            font=("SF Pro Display", 20, "bold"),
            text_color=self.text_color
        )
        self.jobs_title.pack(side="left")
        
        self.jobs_list_frame = ctk.CTkFrame(self.jobs_content, fg_color="transparent")
        self.jobs_list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.jobs_table = ctk.CTkScrollableFrame(
            self.jobs_list_frame,
            fg_color="transparent",
            corner_radius=0
        )
        self.jobs_table.pack(fill="both", expand=True)
        
        # Logs Tab
        self.logs_content = ctk.CTkFrame(self.main_frame, corner_radius=15, fg_color=self.card_color)
        self.logs_content.grid(row=1, column=0, sticky="nsew")
        self.logs_content.grid_remove()
        self.content_frames.append(self.logs_content)
        
        self.logs_header = ctk.CTkFrame(self.logs_content, fg_color="transparent")
        self.logs_header.pack(fill="x", padx=20, pady=15)
        
        self.logs_title = ctk.CTkLabel(
            self.logs_header,
            text="Event Logs",
            font=("SF Pro Display", 20, "bold"),
            text_color=self.text_color
        )
        self.logs_title.pack(side="left")
        
        self.clear_logs_button = ctk.CTkButton(
            self.logs_header,
            text="Clear Logs",
            corner_radius=10,
            fg_color="#E0E0E0",
            text_color=self.text_color,
            hover_color="#BDBDBD",
            width=120,
            height=35,
            font=("SF Pro Text", 14),
            command=self.clear_logs
        )
        self.clear_logs_button.pack(side="right")
        
        self.logs_frame = ctk.CTkFrame(self.logs_content, fg_color="transparent")
        self.logs_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.log_textbox = ctk.CTkTextbox(
            self.logs_frame, 
            font=("SF Pro Mono", 12),
            corner_radius=10,
            border_width=1,
            border_color="#E0E0E0",
            fg_color="#FAFAFA"
        )
        self.log_textbox.pack(fill="both", expand=True)

        # ---------------- Setup macOS Menu Bar ----------------
        self.menu_bar = create_menu_bar_app(self)

        # Event handlers
        self.protocol("WM_DELETE_WINDOW", self.on_minimize)
        self.after(100, self.check_update_queue)

        # Load token if available and auto-connect
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
                button.configure(
                    fg_color=self.primary_color,
                    text_color="#FFFFFF"
                )
            else:
                button.configure(
                    fg_color="transparent",
                    text_color=self.text_color
                )

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
                progress_bar = message['progress_bar']
                try:
                    if progress_bar.winfo_exists():
                        progress_bar.set(message['value'])
                except Exception as e:
                    logging.error(f"Error updating progress bar: {e}")
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
            
            # Update UI to show connected state
            self.after(0, lambda: self.status_indicator.configure(fg_color=self.success_color))
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
                no_printers_label = ctk.CTkLabel(
                    self.printers_list,
                    text="No printers found. Please check your printer connections.",
                    font=("SF Pro Text", 14),
                    text_color=self.secondary_text
                )
                no_printers_label.pack(pady=20)
            
            for printer in self.printers:
                printer_card = ctk.CTkFrame(
                    self.printers_list,
                    corner_radius=10,
                    fg_color="#F9F9F9",
                    border_width=1,
                    border_color="#E0E0E0"
                )
                printer_card.pack(fill="x", padx=5, pady=5)
                
                printer_icon = ctk.CTkLabel(
                    printer_card,
                    text="🖨️",
                    font=("SF Pro Text", 20)
                )
                printer_icon.pack(side="left", padx=(15, 10), pady=15)
                
                printer_info = ctk.CTkFrame(printer_card, fg_color="transparent")
                printer_info.pack(side="left", fill="both", expand=True, pady=10)
                
                printer_name = ctk.CTkLabel(
                    printer_info,
                    text=printer,
                    font=("SF Pro Text", 14, "bold"),
                    text_color=self.text_color,
                    anchor="w"
                )
                printer_name.pack(anchor="w")
                
                printer_status = ctk.CTkLabel(
                    printer_info,
                    text="Ready",
                    font=("SF Pro Text", 12),
                    text_color=self.success_color,
                    anchor="w"
                )
                printer_status.pack(anchor="w")
                
                select_button = ctk.CTkButton(
                    printer_card,
                    text="Select",
                    width=100,
                    height=30,
                    corner_radius=8,
                    fg_color=self.primary_color,
                    hover_color="#1565C0",
                    font=("SF Pro Text", 13),
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
            
            job_card = ctk.CTkFrame(
                self.jobs_table,
                corner_radius=10,
                fg_color="#F9F9F9",
                border_width=1,
                border_color="#E0E0E0"
            )
            job_card.pack(fill="x", padx=5, pady=5)
            
            job_header = ctk.CTkFrame(job_card, fg_color="transparent")
            job_header.pack(fill="x", padx=15, pady=(15, 5))
            
            job_title = ctk.CTkLabel(
                job_header,
                text=f"Job: {job_key}",
                font=("SF Pro Text", 14, "bold"),
                text_color=self.text_color
            )
            job_title.pack(side="left")
            
            job_time = ctk.CTkLabel(
                job_header,
                text=time.strftime("%H:%M:%S"),
                font=("SF Pro Text", 12),
                text_color=self.secondary_text
            )
            job_time.pack(side="right")
            
            job_content = ctk.CTkFrame(job_card, fg_color="transparent")
            job_content.pack(fill="x", padx=15, pady=5)
            
            progress_frame = ctk.CTkFrame(job_content, fg_color="transparent")
            progress_frame.pack(fill="x", pady=5)
            
            progress_bar = ctk.CTkProgressBar(
                progress_frame,
                width=400,
                height=15,
                corner_radius=7,
                fg_color="#E0E0E0",
                progress_color=self.primary_color
            )
            progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))
            progress_bar.set(0)
            
            status_label = ctk.CTkLabel(
                progress_frame,
                text="Downloading...",
                font=("SF Pro Text", 12),
                width=100,
                text_color=self.warning_color
            )
            status_label.pack(side="right")
            
            job_details = ctk.CTkFrame(job_card, fg_color="transparent")
            job_details.pack(fill="x", padx=15, pady=(5, 15))
            
            printer_info = ctk.CTkLabel(
                job_details,
                text=f"Printer: {job_data.get('printer', 'Default')}",
                font=("SF Pro Text", 12),
                text_color=self.secondary_text
            )
            printer_info.pack(side="left")
            
            settings_info = ctk.CTkLabel(
                job_details,
                text=f"Settings: {job_data.get('colorMode', 'Color')}, {job_data.get('paperSize', 'A4')}",
                font=("SF Pro Text", 12),
                text_color=self.secondary_text
            )
            settings_info.pack(side="right")
            
            db.reference(f"users/{user}/jobs/{job_key}").update({"status": "processing"})
            
            def update_progress(progress):
                self.update_queue.put({'type': 'progress', 'progress_bar': progress_bar, 'value': progress})
            
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
            self.after(0, lambda: status_label.configure(text="Downloading...", text_color=self.warning_color))
            
            local_file = download_pdf_from_url(file_url, job_key, progress_callback)
            
            self.after(0, lambda: status_label.configure(text="Printing...", text_color=self.warning_color))
            
            printer_settings = {
                "namePrinter": job_data.get('printer', ''),
                "colorMode": job_data.get('colorMode', 'color'),
                "orientation": job_data.get('orientation', 'portrait'),
                "paperSize": job_data.get('paperSize', 'A4')
            }
            
            success = print_pdf(printer_settings, local_file)
            
            if success:
                self.after(0, lambda: status_label.configure(text="Completed", text_color=self.success_color))
                db.reference(f"users/{user}/jobs/{job_key}").update({"status": "completed"})
            else:
                self.after(0, lambda: status_label.configure(text="Failed", text_color=self.error_color))
                db.reference(f"users/{user}/jobs/{job_key}").update({
                    "status": "error",
                    "error": "Printing failed"
                })
            
            self.update_queue.put({'type': 'log', 'message': f"Job {job_key} {'completed' if success else 'failed'}"})
        except Exception as e:
            self.after(0, lambda: status_label.configure(text="Error", text_color=self.error_color))
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
            logging.error(f"Error quitting app: {e}")
            self.destroy()

if __name__ == "__main__":
    try:
        init_firebase()
        app = PrinterApp()
        app.mainloop()
    except Exception as e:
        logging.error(f"Application error: {e}")
        messagebox.showerror("Error", f"Application error: {e}")
