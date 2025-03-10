from flask import Flask, request, send_file, render_template_string, send_from_directory
import os
from werkzeug.utils import secure_filename
import pandas as pd
from datetime import datetime

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
STATIC_FOLDER = 'static'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(STATIC_FOLDER, exist_ok=True)

# Copy required static files
import shutil
shutil.copy('attached_assets/upload.htm', os.path.join(STATIC_FOLDER, 'index.html'))

@app.route('/')
@app.route('/upload.html')
def upload_form():
    return send_from_directory(STATIC_FOLDER, 'index.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_FOLDER, filename)

@app.route('/upload.php', methods=['POST'])
def upload_file():
    if 'fileToUpload' not in request.files:
        return 'No file part', 400
    file = request.files['fileToUpload']

    if file.filename == '':
        return 'No selected file', 400

    if file and file.filename.endswith('.csv'):
        filename = secure_filename(file.filename)
        input_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(input_path)

        # Process the CSV file (example: add a timestamp column)
        df = pd.read_csv(input_path, sep=';')
        df['ProcessedAt'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Save processed file
        output_filename = f'processed_{filename}'
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        df.to_csv(output_path, sep=';', index=False)

        # Return HTML with download link
        return f'''
        <html>
            <body>
                <h1>File processed successfully</h1>
                <a href="/download/{output_filename}">Download processed file</a>
            </body>
        </html>
        '''
    return 'Invalid file type', 400

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(
        os.path.join(UPLOAD_FOLDER, filename),
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)