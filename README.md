# GPS Image Extractor App

A simple FastAPI + HTML/JS application to scan a folder of images, extract EXIF GPS coordinates, convert them to decimal latitude/longitude, export CSV, and optionally generate an interactive Folium map.

## Features

- Scan a folder recursively for `JPG`, `JPEG`, `PNG`, `TIFF`, `WEBP`
- Extract GPS EXIF metadata from images
- Convert DMS to decimal coordinates
- Handle missing GPS gracefully
- Optional timestamp extraction
- Optional reverse geocoding using OpenStreetMap Nominatim
- Export results to CSV
- Generate interactive HTML map
- Basic browser UI
- REST API endpoints for automation/integration

## Project Structure

```text
gps-image-extractor-app/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   └── scan.py
│   │   └── router.py
│   ├── services/
│   │   ├── exif_service.py
│   │   └── scan_service.py
│   ├── static/
│   │   ├── css/
│   │   │   └── styles.css
│   │   └── js/
│   │       └── app.js
│   ├── templates/
│   │   └── index.html
│   └── main.py
├── data/
│   └── output/
├── requirements.txt
├── run.bat
├── run.sh
└── README.md
```

## How to Run in VS Code

### 1. Extract the ZIP
Unzip the folder anywhere on your system.

### 2. Open in VS Code
Open the extracted project folder in VS Code.

### 3. Create virtual environment
#### Windows
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

#### Linux / macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

### 5. Run the app
#### Windows
```powershell
run.bat
```

#### Linux / macOS
```bash
chmod +x run.sh
./run.sh
```

Or directly:
```bash
uvicorn app.main:app --reload
```

### 6. Open in browser
Open:

```text
http://127.0.0.1:8000
```

---

## API Endpoints

### Health check
```http
GET /health
```

### Scan folder
```http
POST /api/scan
Content-Type: application/json

{
  "folder_path": "C:/Users/YourName/Pictures",
  "reverse_geocode": false,
  "create_map": true
}
```

### Export CSV
```http
POST /api/export-csv
Content-Type: application/json

{
  "folder_path": "C:/Users/YourName/Pictures",
  "reverse_geocode": false,
  "create_map": false
}
```

---

## Notes

- GPS metadata is far more common in JPEG/JPG files than PNG.
- Reverse geocoding needs internet access.
- Public Nominatim usage should be rate-limited for very large batches.
- Output files are written under `data/output/`.

