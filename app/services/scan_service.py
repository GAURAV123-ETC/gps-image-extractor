from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import folium
import pandas as pd
import requests

from app.services.exif_service import extract_metadata

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "output"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "gps-image-extractor-app/1.0"


def find_images(folder_path: str) -> List[str]:
    image_paths: List[str] = []
    base = Path(folder_path)
    for path in base.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            image_paths.append(str(path))
    return sorted(image_paths)


def reverse_geocode(lat: float, lon: float, timeout: int = 10) -> Optional[str]:
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                "format": "jsonv2",
                "lat": lat,
                "lon": lon,
                "zoom": 16,
                "addressdetails": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("display_name")
    except Exception:
        return None


def generate_map(df: pd.DataFrame) -> Optional[str]:
    gps_df = df.dropna(subset=["latitude", "longitude"]).copy()
    if gps_df.empty:
        return None

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    center_lat = float(gps_df["latitude"].mean())
    center_lon = float(gps_df["longitude"].mean())

    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=5)

    for _, row in gps_df.iterrows():
        popup = (
            f"<b>Image:</b> {row.get('image_name', '')}<br>"
            f"<b>Latitude:</b> {row.get('latitude', '')}<br>"
            f"<b>Longitude:</b> {row.get('longitude', '')}<br>"
            f"<b>Timestamp:</b> {row.get('timestamp', '')}<br>"
            f"<b>Location:</b> {row.get('location_name') or 'N/A'}"
        )
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=folium.Popup(popup, max_width=350),
            tooltip=row.get("image_name", "Image"),
        ).add_to(fmap)

    filename = f"gps_map_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    out_path = OUTPUT_DIR / filename
    fmap.save(str(out_path))
    return str(out_path)


def save_to_csv(df: pd.DataFrame, output_dir: Optional[Path] = None) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if output_dir is None:
        output_dir = OUTPUT_DIR
    else:
        output_dir = Path(output_dir)

    filename = f"gps_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    output_path = output_dir / filename
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    return str(output_path)


def save_to_excel(df: pd.DataFrame, output_dir: Optional[Path] = None) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if output_dir is None:
        output_dir = OUTPUT_DIR
    else:
        output_dir = Path(output_dir)

    filename = f"gps_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    output_path = output_dir / filename
    
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='GPS Data')
        workbook = writer.book
        worksheet = writer.sheets['GPS Data']
        
        # Auto-adjust column widths
        for col in worksheet.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            worksheet.column_dimensions[column].width = adjusted_width

    return str(output_path)


def process_folder(folder_path: str, reverse_geocode_enabled: bool = False, create_map: bool = True) -> Tuple[pd.DataFrame, Optional[str]]:
    records = []
    image_files = find_images(folder_path)

    for image_path in image_files:
        record = extract_metadata(image_path)
        if reverse_geocode_enabled and record["latitude"] is not None and record["longitude"] is not None:
            record["location_name"] = reverse_geocode(record["latitude"], record["longitude"])
            time.sleep(1)
        else:
            record["location_name"] = None
        records.append(record)

    df = pd.DataFrame(records)
    map_path = generate_map(df) if create_map and not df.empty else None
    return df, map_path
