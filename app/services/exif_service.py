from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import GPSTAGS

GPS_IFD_TAG = 34853


def rational_to_float(value: Any) -> float:
    """Convert a PIL EXIF rational/tuple/number into float."""
    try:
        return float(value)
    except Exception:
        pass

    try:
        numerator = getattr(value, "numerator")
        denominator = getattr(value, "denominator")
        return float(numerator) / float(denominator)
    except Exception:
        pass

    if isinstance(value, tuple) and len(value) == 2:
        return float(value[0]) / float(value[1])

    text = str(value)
    if "/" in text:
        num, den = text.split("/", 1)
        return float(num) / float(den)

    return float(text)


def dms_to_decimal(dms: Iterable[Any], ref: str) -> Optional[float]:
    try:
        parts = list(dms)
        if len(parts) != 3:
            return None

        degrees = rational_to_float(parts[0])
        minutes = rational_to_float(parts[1])
        seconds = rational_to_float(parts[2])
        decimal = degrees + minutes / 60.0 + seconds / 3600.0

        if ref.upper() in {"S", "W"}:
            decimal *= -1
        return decimal
    except Exception:
        return None


def decode_gps_info(gps_ifd: Dict[int, Any]) -> Dict[str, Any]:
    decoded: Dict[str, Any] = {}
    for key, value in gps_ifd.items():
        name = GPSTAGS.get(key, key)
        decoded[name] = value
    return decoded


def extract_coords_from_ocr(image_source: Any) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """Try to extract visible Lat: / Long: text from an image using OCR (pytesseract)."""
    try:
        import pytesseract
    except ImportError:
        return None, None, "pytesseract not installed"

    # Auto-detect Tesseract installation path on Windows
    import shutil, os
    if not shutil.which("tesseract"):
        common_paths = [
            os.path.expanduser(r"~\scoop\shims\tesseract.exe"),      # Scoop install
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",          # Standard install
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
        ]
        for p in common_paths:
            if os.path.isfile(p):
                pytesseract.pytesseract.tesseract_cmd = p
                break
        else:
            return None, None, "Tesseract binary not found. Please install from https://github.com/UB-Mannheim/tesseract/wiki"

    try:
        # Reset file pointer if it's a stream
        if hasattr(image_source, "seek"):
            image_source.seek(0)

        img = Image.open(image_source)

        # 1. Generous crop for wide images (like multi-page shots)
        crop_box = (0, 0, int(img.width * 0.55), int(img.height * 0.35))
        img = img.crop(crop_box)

        if img.mode != "RGB":
            img = img.convert("RGB")
            
        r, g, b = img.split()
        
        # 2. 'Nuclear' Blue Isolation: subtract BOTH Red and Green from Blue
        # This ensures that only pixels that are primarily blue survive.
        # Black text, white paper, and brown desks all get zeroed out.
        from PIL import ImageChops, ImageOps
        diff_r = ImageChops.subtract(b, r)
        diff_g = ImageChops.subtract(b, g)
        
        # Multiply diffs to ensure the pixel is strongly 'Blue-Dominant'
        blue_ish = ImageChops.multiply(diff_r, diff_g)
        
        # 3. Autocontrast, Invert and Scale Up
        # Autocontrast makes the isolated blue text pop intensely against the darkness.
        blue_ish = ImageOps.autocontrast(blue_ish)
        final_img = ImageOps.invert(blue_ish)
        
        new_size = (final_img.width * 3, final_img.height * 3)
        final_img = final_img.resize(new_size, Image.Resampling.LANCZOS)
        
        # 4. Use PSM 6 (Single uniform block of text) - most stable for isolated text
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(final_img, config=custom_config)

        # Normalize common OCR mistakes
        # Smart regex to catch coordinates even if labels are missing or symbols
        # We now parse line-by-line to avoid date/timestamp interference
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # 1. Filter out the date line (e.g. "Jan 19, 2026")
        months = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|AM|PM)'
        data_lines = []
        for line in lines:
            if not re.search(months, line, re.IGNORECASE):
                data_lines.append(line)

        def extract_from_line(line):
            # 1. Standard match: "27.218" or "27 218" or "27,218"
            match = re.search(r'(-?\d{1,3})[.,\s]+(\d+)', line)
            if match:
                return float(f"{match.group(1)}.{match.group(2)}")
            
            # 2. Fallback: 8+ digit string missing a dot (e.g. "779319101")
            # We assume a dot after the first 2 digits for coordinates in India (19.. or 77..)
            match_long = re.search(r'(\d{2})(\d{5,})', line)
            if match_long:
                return float(f"{match_long.group(1)}.{match_long.group(2)}")
            return None

        lat = None
        lon = None
        
        # 2. Assign coordinates based on remaining lines and keywords
        for line in data_lines:
            val = extract_from_line(line)
            if val is None:
                continue
            
            # Check for explicit labels
            is_lat = any(x in line.lower() for x in ["lat", "let", "lats"])
            is_lon = any(x in line.lower() for x in ["lon", "lomg", "lons"])
            
            if is_lat:
                lat = val
            elif is_lon:
                lon = val
            elif lat is None: # First line with numbers is likely Lat
                lat = val
            elif lon is None: # Second line is likely Lon
                lon = val

        # 3. Final sanity check for coordinate ranges (specific to India for these images)
        if lat and not (10 < lat < 40): lat = None
        if lon and not (60 < lon < 100): lon = None

        return lat, lon, text.strip()
    except Exception as e:
        return None, None, f"OCR error: {e}"


def extract_metadata(image_source: Any, filename: Optional[str] = None) -> Dict[str, Any]:
    """Extract GPS latitude/longitude and timestamp from an image path or file-like object.
    Falls back to OCR text extraction if EXIF GPS is missing.
    """
    is_path = isinstance(image_source, (str, Path))

    if is_path:
        file_path = Path(image_source)
        computed_name = file_path.name
        img_path_str = str(file_path.resolve())
    else:
        computed_name = filename or "uploaded_image"
        img_path_str = "memory"

    result: Dict[str, Any] = {
        "image_name": computed_name,
        "image_path": img_path_str,
        "latitude": None,
        "longitude": None,
        "timestamp": None,
        "status": "No GPS data",
        "error": None,
    }

    try:
        with Image.open(image_source) as img:
            exif = img.getexif()
            if not exif:
                result["status"] = "No EXIF metadata"
                # Fall through to OCR below
            else:
                timestamp = exif.get(36867) or exif.get(36868) or exif.get(306)
                if timestamp:
                    result["timestamp"] = str(timestamp)

                gps_ifd = exif.get_ifd(GPS_IFD_TAG) if GPS_IFD_TAG in exif else None
                if gps_ifd:
                    gps = decode_gps_info(gps_ifd)
                    lat = gps.get("GPSLatitude")
                    lat_ref = gps.get("GPSLatitudeRef")
                    lon = gps.get("GPSLongitude")
                    lon_ref = gps.get("GPSLongitudeRef")

                    if isinstance(lat_ref, bytes):
                        lat_ref = lat_ref.decode(errors="ignore")
                    if isinstance(lon_ref, bytes):
                        lon_ref = lon_ref.decode(errors="ignore")

                    if lat and lat_ref and lon and lon_ref:
                        latitude = dms_to_decimal(lat, str(lat_ref))
                        longitude = dms_to_decimal(lon, str(lon_ref))
                        if latitude is not None and longitude is not None:
                            result["latitude"] = latitude
                            result["longitude"] = longitude
                            result["status"] = "GPS extracted (EXIF)"
                            return result
                        else:
                            result["status"] = "Unsupported GPS format"
                    else:
                        result["status"] = "No GPS data"

    except UnidentifiedImageError:
        result["status"] = "Unsupported or corrupted image"
        result["error"] = "Pillow could not identify this image file"
        return result
    except OSError as exc:
        result["status"] = "Unsupported or corrupted image"
        result["error"] = str(exc)
        return result
    except Exception as exc:
        result["status"] = "Error"
        result["error"] = str(exc)
        return result

    # --- OCR Fallback ---
    # If no EXIF GPS found, try reading visible Lat/Long text in the image
    lat, lon, ocr_text = extract_coords_from_ocr(image_source)
    if lat is not None and lon is not None:
        result["latitude"] = lat
        result["longitude"] = lon
        result["status"] = "GPS extracted (OCR)"
    else:
        # Surface OCR text to the user so they can debug what Tesseract saw
        if ocr_text:
            result["status"] = "OCR found no GPS"
            # Show the first 100 chars of extracted text in the error column
            cleaned = ocr_text.replace('\n', ' | ')
            result["error"] = f"Raw text: {cleaned[:100]}"
        elif result["status"] not in ("Unsupported GPS format",):
            result["status"] = "No GPS data"

    return result
