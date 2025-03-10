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
from config import *

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CSVUploader:
    def __init__(self):
        self.session = requests.Session()
    
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
            # Find download link in response
            download_link = None

            # Look for href links in response
            from bs4 import BeautifulSoup
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

            # Get filename from Content-Disposition header or URL
            content_disposition = download_response.headers.get('content-disposition')
            if content_disposition and 'filename=' in content_disposition:
                # Extract filename from content-disposition
                import re
                filename_match = re.search(r'filename=(.+)', content_disposition)
                if filename_match:
                    filename = filename_match.group(1).strip('"').strip()
                else:
                    filename = os.path.basename(download_link)
            else:
                filename = os.path.basename(download_link)

            output_path = os.path.join(output_dir, filename)
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

        # This line should never be reached due to the raise in the loop,
        # but we add it to satisfy the type checker
        raise ValueError(f"Processing failed: {str(last_error)}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python csv_uploader.py <input_csv_file> <output_directory>")
        sys.exit(1)
        
    input_file = sys.argv[1]
    output_dir = sys.argv[2]
    
    try:
        uploader = CSVUploader()
        result_path = uploader.process_file(input_file, output_dir)
        print(f"Successfully processed file. Result saved to: {result_path}")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()