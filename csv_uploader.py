#!/usr/bin/env python3
"""
CSV File Uploader
Automates uploading CSV files to a web form and handles the response/download
"""

import os
import sys
import time
import requests
from pathlib import Path
from urllib.parse import urljoin
import logging
from bs4 import BeautifulSoup
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('csv_uploader.log')  # Also log to file for debugging
    ]
)
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "UPLOAD_PAGE_URL": "http://localhost:5000/upload.html",
    "UPLOAD_ENDPOINT": "http://localhost:5000/upload.php",
    "ALLOWED_EXTENSIONS": ['.csv'],
    "ALLOWED_DOWNLOAD_EXTENSIONS": ['.csv', '.zip', '.rar'],
    "MAX_RETRIES": 3,
    "RETRY_DELAY": 2,
    "TIMEOUT": 1200  # 20 minutes in seconds
}

# Try to import config, use defaults if not found
try:
    from config import *
except ImportError:
    logger.warning("Config file not found, using default settings")
    UPLOAD_PAGE_URL = DEFAULT_CONFIG["UPLOAD_PAGE_URL"]
    UPLOAD_ENDPOINT = DEFAULT_CONFIG["UPLOAD_ENDPOINT"]
    ALLOWED_EXTENSIONS = DEFAULT_CONFIG["ALLOWED_EXTENSIONS"]
    ALLOWED_DOWNLOAD_EXTENSIONS = DEFAULT_CONFIG["ALLOWED_DOWNLOAD_EXTENSIONS"]
    MAX_RETRIES = DEFAULT_CONFIG["MAX_RETRIES"]
    RETRY_DELAY = DEFAULT_CONFIG["RETRY_DELAY"]
    TIMEOUT = DEFAULT_CONFIG["TIMEOUT"]

class CSVUploader:
    def __init__(self):
        self.session = requests.Session()
        self.original_filename = None  # Store original filename

    def validate_file(self, file_path: str) -> bool:
        """
        Validate if the provided file exists and is a CSV
        """
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return False

        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            logger.error(f"Invalid file type. Must be CSV: {file_path}")
            return False

        # Check if file is not empty
        if path.stat().st_size == 0:
            logger.error(f"File is empty: {file_path}")
            return False

        return True

    def upload_file(self, file_path: str) -> requests.Response:
        """
        Upload the CSV file to the server
        """
        try:
            # Store original filename without extension
            self.original_filename = os.path.splitext(os.path.basename(file_path))[0]

            with open(file_path, 'rb') as f:
                files = {
                    'fileToUpload': (os.path.basename(file_path), f, 'text/csv')
                }
                data = {
                    'submit': 'Upload CSV'
                }

                logger.info(f"Uploading file: {file_path}")
                response = self.session.post(
                    UPLOAD_ENDPOINT,
                    files=files,
                    data=data,
                    timeout=TIMEOUT
                )
                response.raise_for_status()
                return response

        except requests.exceptions.RequestException as e:
            logger.error(f"Upload failed: {str(e)}")
            raise

    def download_result(self, response: requests.Response, output_dir: str) -> str:
        """
        Extract download link from response and download the file
        """
        try:
            download_link = None

            # Look for href links in response
            soup = BeautifulSoup(response.text, 'html.parser')
            for link in soup.find_all('a'):
                href = link.get('href')
                if href:
                    ext = Path(href).suffix.lower()
                    if ext in ALLOWED_DOWNLOAD_EXTENSIONS:
                        download_link = urljoin(UPLOAD_ENDPOINT, href)
                        break

            if not download_link:
                logger.error("No download link found in response")
                raise ValueError("No download link found in response")

            # Download the file
            logger.info(f"Downloading result from: {download_link}")
            download_response = self.session.get(download_link, timeout=TIMEOUT)
            download_response.raise_for_status()

            # Get the extension from Content-Type or download link
            ext = os.path.splitext(download_link)[1]
            if not ext:
                content_type = download_response.headers.get('content-type', '')
                if 'zip' in content_type:
                    ext = '.zip'
                elif 'rar' in content_type:
                    ext = '.rar'
                else:
                    ext = '.csv'  # default to csv if unknown

            # Use original filename with new extension
            filename = f"{self.original_filename}{ext}" if self.original_filename else f"processed_{int(time.time())}{ext}"

            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)

            # Ensure the output path is absolute
            output_path = os.path.abspath(os.path.join(output_dir, filename))

            # Write file with proper encoding handling
            with open(output_path, 'wb') as f:
                f.write(download_response.content)

            logger.info(f"Result saved to: {output_path}")
            return output_path

        except (requests.exceptions.RequestException, ValueError) as e:
            logger.error(f"Download failed: {str(e)}")
            raise

    def process_file(self, input_file: str, output_dir: str) -> str:
        """
        Main process to handle file upload and download
        Returns: Path to the downloaded result file
        Raises: ValueError if validation fails or processing fails after max retries
        """
        if not self.validate_file(input_file):
            raise ValueError("File validation failed")

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Upload with retry logic
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.upload_file(input_file)
                result_path = self.download_result(response, output_dir)
                return result_path

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error("Max retries reached")
                    raise ValueError(f"Processing failed after {MAX_RETRIES} attempts: {str(last_error)}")

        # This line should never be reached due to the raise in the loop
        raise ValueError(f"Processing failed: {str(last_error)}")

def main():
    # If running as executable and no arguments provided, use GUI file picker
    if getattr(sys, 'frozen', False) and len(sys.argv) == 1:
        try:
            import tkinter as tk
            from tkinter import filedialog, messagebox

            root = tk.Tk()
            root.withdraw()  # Hide the main window

            # Get input file
            input_file = filedialog.askopenfilename(
                title="Select CSV file to upload",
                filetypes=[("CSV files", "*.csv")]
            )
            if not input_file:
                sys.exit(0)

            # Get output directory
            output_dir = filedialog.askdirectory(
                title="Select output directory for processed files"
            )
            if not output_dir:
                sys.exit(0)

        except Exception as e:
            error_msg = f"Error with file selection: {str(e)}"
            print(error_msg)
            try:
                import tkinter.messagebox as messagebox
                messagebox.showerror("Error", error_msg)
            except:
                pass  # If messagebox fails, at least we printed the error
            sys.exit(1)

    elif len(sys.argv) != 3:
        print("Usage: python csv_uploader.py <input_csv_file> <output_directory>")
        print("   or: Run the executable without arguments to use the file picker")
        sys.exit(1)
    else:
        input_file = sys.argv[1]
        output_dir = sys.argv[2]

    try:
        uploader = CSVUploader()
        result_path = uploader.process_file(input_file, output_dir)
        success_msg = f"Successfully processed file. Result saved to: {result_path}"
        print(success_msg)

        # Show message box if running as executable
        if getattr(sys, 'frozen', False):
            try:
                import tkinter.messagebox as messagebox
                messagebox.showinfo("Success", success_msg)
            except:
                pass  # If messagebox fails, we already printed the message

        sys.exit(0)

    except Exception as e:
        error_msg = f"Processing failed: {str(e)}"
        logger.error(error_msg)

        # Show error in message box if running as executable
        if getattr(sys, 'frozen', False):
            try:
                import tkinter.messagebox as messagebox
                messagebox.showerror("Error", error_msg)
            except:
                pass  # If messagebox fails, we already logged the error

        sys.exit(1)

if __name__ == "__main__":
    main()