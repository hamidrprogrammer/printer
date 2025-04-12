# PrinterSync Pro - macOS Edition

This is the macOS version of PrinterSync Pro, a printer management application that connects to Firebase, lists available printers, and handles print jobs automatically.

## Features

- Modern macOS-style user interface
- Firebase integration for remote print job management
- Automatic printer detection using CUPS
- Automatic PDF printing
- System menu bar integration
- Real-time print job status updates

## Installation Instructions

### Prerequisites

- macOS 10.14 or later
- Python 3.8 or later
- pip (Python package manager)

### Step 1: Install Dependencies

Open Terminal and run:

```bash
pip3 install -r requirements.txt
```

### Step 2: Configure Firebase

Place your `serviceAccountKey.json` file in the same directory as the application files.

### Step 3: Test the Application

Run the application directly to test:

```bash
python3 main_mac.py
```

### Step 4: Create DMG File for Distribution

To create a standalone application and DMG file:

```bash
python3 create_dmg.py
```

This will create a DMG file in the `dist` directory that can be distributed to other macOS users.

## File Structure

- `main_mac.py` - Main application code
- `setup.py` - Configuration for py2app to create macOS application bundle
- `create_dmg.py` - Script to create DMG file for distribution
- `requirements.txt` - Required Python packages
- `icons/app_icon.icns` - Application icon (placeholder - replace with your own)

## Usage

1. Launch the application
2. Enter your Firebase connection token
3. The application will connect to Firebase and display available printers
4. Print jobs sent to your account will be automatically processed

## Differences from Windows Version

- Uses CUPS instead of win32print for printer management
- Uses native macOS printing commands instead of SumatraPDF
- Uses macOS menu bar instead of Windows system tray
- Modern UI design optimized for macOS

## Troubleshooting

- If you encounter issues with printer detection, ensure CUPS is properly configured on your system
- For Firebase connection issues, verify your serviceAccountKey.json file is valid
- If the application fails to start, check the log file for detailed error messages

## Notes for Developers

- The application uses the CUPS Python module for printer management
- Firebase integration is maintained exactly as in the Windows version
- The UI is built with customtkinter for a modern macOS look and feel
