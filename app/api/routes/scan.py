from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.scan_service import process_folder, save_to_csv

router = APIRouter()


class ScanRequest(BaseModel):
    folder_path: str = Field(..., description="Folder containing images")
    reverse_geocode: bool = False
    create_map: bool = True


@router.post("/scan")
def scan_folder(payload: ScanRequest):
    folder = Path(payload.folder_path)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail="Invalid folder path.")

    df, map_path = process_folder(
        folder_path=str(folder),
        reverse_geocode_enabled=payload.reverse_geocode,
        create_map=payload.create_map,
    )

    # Safely convert NaN and Inf to None for JSON serialization
    records = df.astype(object).where(pd.notnull(df), None).to_dict(orient="records") if not df.empty else []
    with_gps = sum(1 for row in records if row.get("latitude") is not None and row.get("longitude") is not None)

    return {
        "message": "Scan completed",
        "total_files": len(records),
        "with_gps": with_gps,
        "without_gps": len(records) - with_gps,
        "map_file": map_path,
        "results": records,
    }


@router.post("/export-csv")
def export_csv(payload: ScanRequest):
    folder = Path(payload.folder_path)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail="Invalid folder path.")

    df, _ = process_folder(
        folder_path=str(folder),
        reverse_geocode_enabled=payload.reverse_geocode,
        create_map=payload.create_map,
    )

    if df.empty:
        raise HTTPException(status_code=404, detail="No supported image files found.")

    csv_path = save_to_csv(df, output_dir=folder)
    return FileResponse(path=csv_path, media_type="text/csv", filename=Path(csv_path).name)


@router.post("/export-excel")
def export_excel(payload: ScanRequest):
    folder = Path(payload.folder_path)
    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail="Invalid folder path.")

    df, _ = process_folder(
        folder_path=str(folder),
        reverse_geocode_enabled=payload.reverse_geocode,
        create_map=payload.create_map,
    )

    if df.empty:
        raise HTTPException(status_code=404, detail="No supported image files found.")

    from app.services.scan_service import save_to_excel
    excel_path = save_to_excel(df, output_dir=folder)
    return FileResponse(
        path=excel_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=Path(excel_path).name
    )


@router.get("/browse-folder")
def browse_folder():
    import tkinter as tk
    from tkinter import filedialog
    # Need to run tkinter in main thread typically, but for local FastAPI it often works
    # if we hide the main window carefully.
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder_path = filedialog.askdirectory(title="Select Folder containing Images")
    root.destroy()
    return {"folder_path": folder_path}


from fastapi import UploadFile, File, Form
from typing import List
import pandas as pd
from app.services.exif_service import extract_metadata
from app.services.scan_service import generate_map, reverse_geocode
import time

@router.post("/scan-upload")
def scan_upload(
    files: List[UploadFile] = File(...),
    reverse_geocode_enabled: bool = Form(False),
    create_map: bool = Form(True)
):
    records = []
    
    for file in files:
        contents = file.file
        record = extract_metadata(contents, filename=file.filename)
        if reverse_geocode_enabled and record["latitude"] is not None and record["longitude"] is not None:
            record["location_name"] = reverse_geocode(record["latitude"], record["longitude"])
            time.sleep(1)
        else:
            record["location_name"] = None
        records.append(record)

    df = pd.DataFrame(records)
    map_path = generate_map(df) if create_map and not df.empty else None

    # Safely convert NaN and Inf to None for JSON serialization
    records_dict = df.astype(object).where(pd.notnull(df), None).to_dict(orient="records") if not df.empty else []
    with_gps = sum(1 for row in records_dict if row.get("latitude") is not None and row.get("longitude") is not None)

    return {
        "message": "Upload scan completed",
        "total_files": len(records_dict),
        "with_gps": with_gps,
        "without_gps": len(records_dict) - with_gps,
        "map_file": map_path,
        "results": records_dict,
    }
