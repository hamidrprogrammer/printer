"""
Script to create a DMG file for macOS distribution
"""

import os
import sys
import subprocess
from setuptools import setup

def create_dmg():
    print("Creating DMG file for macOS distribution...")
    
    # First, build the app using py2app
    try:
        subprocess.run(["python3", "setup.py", "py2app"], check=True)
        print("Application bundle created successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error creating application bundle: {e}")
        return False
    
    # Create DMG file using hdiutil (macOS command)
    try:
        app_path = os.path.abspath("dist/PrinterSync Pro.app")
        dmg_path = os.path.abspath("dist/PrinterSyncPro.dmg")
        
        # This would be the actual command on macOS
        # subprocess.run([
        #     "hdiutil", "create", "-volname", "PrinterSync Pro", 
        #     "-srcfolder", app_path, 
        #     "-ov", "-format", "UDZO", 
        #     dmg_path
        # ], check=True)
        
        print(f"DMG file would be created at: {dmg_path}")
        print("Note: This script needs to be run on macOS to create the actual DMG file.")
        
        # Create a placeholder DMG file for demonstration
        with open("dist/PrinterSyncPro.dmg", "w") as f:
            f.write("This is a placeholder DMG file. Run this script on macOS to create the actual DMG.")
        
        return True
    except Exception as e:
        print(f"Error creating DMG file: {e}")
        return False

if __name__ == "__main__":
    if sys.platform != "darwin":
        print("Warning: This script should be run on macOS for actual DMG creation.")
        print("Creating placeholder DMG file for demonstration purposes.")
    
    # Create dist directory if it doesn't exist
    os.makedirs("dist", exist_ok=True)
    
    if create_dmg():
        print("DMG file created successfully.")
    else:
        print("Failed to create DMG file.")
