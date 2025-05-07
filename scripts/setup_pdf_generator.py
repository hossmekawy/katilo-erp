#!/usr/bin/env python3
import os
import sys
import platform
import subprocess
import shutil

# Define the local wkhtmltopdf path
LOCAL_WKHTMLTOPDF_PATH = os.path.join('pdftool', 'wkhtmltopdf', 'bin', 'wkhtmltopdf.exe')
ABSOLUTE_WKHTMLTOPDF_PATH = os.path.abspath(LOCAL_WKHTMLTOPDF_PATH)

def check_wkhtmltopdf_installed():
    """Check if wkhtmltopdf is installed and accessible"""
    # First check if the local copy exists
    if os.path.exists(LOCAL_WKHTMLTOPDF_PATH):
        try:
            result = subprocess.run([LOCAL_WKHTMLTOPDF_PATH, '--version'], 
                                  stdout=subprocess.PIPE, 
                                  stderr=subprocess.PIPE)
            if result.returncode == 0:
                print(f"Found local wkhtmltopdf at: {ABSOLUTE_WKHTMLTOPDF_PATH}")
                return True
        except Exception as e:
            print(f"Error checking local wkhtmltopdf: {str(e)}")
    
    # If local copy doesn't exist or doesn't work, check system PATH
    try:
        result = subprocess.run(['wkhtmltopdf', '--version'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE)
        if result.returncode == 0:
            print("Found wkhtmltopdf in system PATH")
            return True
    except FileNotFoundError:
        pass
    
    return False

def install_wkhtmltopdf():
    """Install wkhtmltopdf based on the operating system"""
    system = platform.system().lower()
    
    if system == 'windows':
        print("For Windows, checking if the local copy exists in the expected location...")
        if os.path.exists(LOCAL_WKHTMLTOPDF_PATH):
            print(f"Local wkhtmltopdf already exists at: {ABSOLUTE_WKHTMLTOPDF_PATH}")
            return True
        
        print("Local wkhtmltopdf not found.")
        print("Please download wkhtmltopdf and extract it to the following location:")
        print(f"  {ABSOLUTE_WKHTMLTOPDF_PATH}")
        print("Download from: https://wkhtmltopdf.org/downloads.html")
        return False
    
    elif system == 'linux':
        # For Debian/Ubuntu
        if os.path.exists('/etc/debian_version'):
            print("Installing wkhtmltopdf for Debian/Ubuntu...")
            subprocess.run(['sudo', 'apt-get', 'update'])
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'wkhtmltopdf'])
        # For RHEL/CentOS/Fedora
        elif os.path.exists('/etc/redhat-release'):
            print("Installing wkhtmltopdf for RHEL/CentOS/Fedora...")
            subprocess.run(['sudo', 'yum', 'install', '-y', 'wkhtmltopdf'])
        else:
            print("Unsupported Linux distribution. Please install wkhtmltopdf manually.")
            print("Visit: https://wkhtmltopdf.org/downloads.html")
            return False
    
    elif system == 'darwin':  # macOS
        print("Installing wkhtmltopdf for macOS using Homebrew...")
        # Check if Homebrew is installed
        try:
            subprocess.run(['brew', '--version'], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE)
        except FileNotFoundError:
            print("Homebrew not found. Please install Homebrew first:")
            print("/bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
            return False
        
        # Install wkhtmltopdf using Homebrew
        subprocess.run(['brew', 'install', 'wkhtmltopdf'])
    
    else:
        print(f"Unsupported operating system: {system}")
        print("Please install wkhtmltopdf manually: https://wkhtmltopdf.org/downloads.html")
        return False
    
    return check_wkhtmltopdf_installed()

def main():
    print("Checking if wkhtmltopdf is installed...")
    
    if check_wkhtmltopdf_installed():
        print("wkhtmltopdf is already installed and accessible!")
        return 0
    
    print("wkhtmltopdf is not installed or not accessible.")
    
    if install_wkhtmltopdf():
        print("wkhtmltopdf has been successfully installed!")
        return 0
    else:
        print("Failed to install wkhtmltopdf automatically.")
        print("Please install it manually from: https://wkhtmltopdf.org/downloads.html")
        return 1

if __name__ == "__main__":
    sys.exit(main())
