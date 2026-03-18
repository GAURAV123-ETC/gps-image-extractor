from __future__ import annotations

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


def extract_metadata(image_source: Any, filename: Optional[str] = None) -> Dict[str, Any]:
    """Extract GPS latitude/longitude and timestamp from an image path or file-like object."""
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
                return result

            timestamp = exif.get(36867) or exif.get(36868) or exif.get(306)
            if timestamp:
                result["timestamp"] = str(timestamp)

            gps_ifd = exif.get_ifd(GPS_IFD_TAG) if GPS_IFD_TAG in exif else None
            if not gps_ifd:
                result["status"] = "No GPS data"
                return result

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
                    result["status"] = "GPS extracted"
                else:
                    result["status"] = "Unsupported GPS format"
            else:
                result["status"] = "No GPS data"

    except UnidentifiedImageError:
        result["status"] = "Unsupported or corrupted image"
        result["error"] = "Pillow could not identify this image file"
    except OSError as exc:
        result["status"] = "Unsupported or corrupted image"
        result["error"] = str(exc)
    except Exception as exc:
        result["status"] = "Error"
        result["error"] = str(exc)

    return result
