"""Configuration settings for the CSV uploader"""

# URLs
UPLOAD_PAGE_URL = "http://localhost:5000/upload.html"
UPLOAD_ENDPOINT = "http://localhost:5000/upload.php"

# File handling settings
ALLOWED_EXTENSIONS = ['.csv']
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Request timeout settings
TIMEOUT = 30  # seconds