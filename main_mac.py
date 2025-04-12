import os
import customtkinter as ctk

# تنظیم متغیر محیطی برای پنهان‌سازی هشدارهای Tk در macOS
os.environ["TK_SILENCE_DEPRECATION"] = "1"

# تنظیم حالت ظاهری و تم رنگی
ctk.set_appearance_mode("dark")  # می‌توانید "light" را نیز امتحان کنید
ctk.set_default_color_theme("blue")

class PrinterApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("PrinterSync Pro")
        self.geometry("1100x800")
        self.minsize(900, 650)
        
        # بخش سرصفحه با رنگ زمینه‌ی آبی
        header_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#1976D2")
        header_frame.pack(fill="x", padx=20, pady=20)
        
        title_label = ctk.CTkLabel(
            header_frame,
            text="PrinterSync Pro",
            font=("SF Pro Display", 32, "bold"),
            text_color="#FFFFFF"
        )
        title_label.pack(side="left", padx=10, pady=10)
        
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="macOS Edition",
            font=("SF Pro Text", 16),
            text_color="#E1F5FE"
        )
        subtitle_label.pack(side="left", padx=10, pady=10)
        
        # بخش ورود توکن
        token_frame = ctk.CTkFrame(self, corner_radius=15, fg_color="#FFFFFF")
        token_frame.pack(fill="x", padx=20, pady=10)
        
        token_header = ctk.CTkLabel(
            token_frame,
            text="Connect Your Account",
            font=("SF Pro Display", 18, "bold"),
            text_color="#212121"
        )
        token_header.pack(anchor="w", padx=20, pady=(15, 5))
        
        token_desc = ctk.CTkLabel(
            token_frame,
            text="Enter your connection token to link this device with your account",
            font=("SF Pro Text", 14),
            text_color="#757575"
        )
        token_desc.pack(anchor="w", padx=20, pady=(0, 15))
        
        self.token_entry = ctk.CTkEntry(
            token_frame,
            width=600,
            placeholder_text="Paste your token here",
            font=("SF Pro Text", 14),
            height=40,
            corner_radius=10
        )
        self.token_entry.pack(padx=20, pady=10)
        
        connect_button = ctk.CTkButton(
            token_frame,
            text="Connect",
            command=self.connect,
            font=("SF Pro Text", 14, "bold"),
            fg_color="#2196F3",
            width=150,
            height=40,
            corner_radius=10
        )
        connect_button.pack(pady=(0, 15))
        
        # برچسب وضعیت اتصال
        self.status_label = ctk.CTkLabel(
            self,
            text="Status: Disconnected",
            font=("SF Pro Text", 14),
            text_color="#F44336"
        )
        self.status_label.pack(padx=20, pady=10)
    
    def connect(self):
        token = self.token_entry.get().strip()
        if token:
            self.status_label.configure(text="Status: Connected", text_color="#4CAF50")
            print("Connected with token:", token)
            # در اینجا می‌توانید کد اتصال به Firebase یا سایر منطق‌های مورد نظر را اضافه کنید.
        else:
            self.status_label.configure(text="Status: Disconnected", text_color="#F44336")
            print("No token provided!")

if __name__ == "__main__":
    app = PrinterApp()
    app.mainloop()
