from datetime import datetime, timedelta
from pathlib import Path
import shutil
import os

def get_current_date_str():
    from data_manager import APP_DATE_FORMAT
    return datetime.now().strftime(APP_DATE_FORMAT)

def get_input_dir(date_str=None):
    if not date_str:
        date_str = get_current_date_str()
    path = Path("input_file") / date_str
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_output_dir(date_str=None):
    if not date_str:
        date_str = get_current_date_str()
    path = Path("output") / date_str
    path.mkdir(parents=True, exist_ok=True)
    return path

def save_uploaded_file(uploaded_file):
    # Always save uploads to TODAY's folder to avoid confusing history
    input_dir = get_input_dir() 
    file_path = input_dir / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

def get_output_path(input_filename, date_str=None, suffix="_analysis.png"):
    output_dir = get_output_dir(date_str)
    base_name = Path(input_filename).stem
    return output_dir / f"{base_name}{suffix}"

def get_available_dates():
    """Finds all folders in input_file/ that match YYYY-MM-DD."""
    dates = []
    input_root = Path("input_file")
    if input_root.exists():
        for item in input_root.iterdir():
            if item.is_dir() and len(item.name) == 10: # Simple YYYY-MM-DD check
                dates.append(item.name)
    
    today = get_current_date_str()
    if today not in dates:
        dates.append(today)
    
    return sorted(list(set(dates)), reverse=True)

def get_last_sync_info(date_str):
    """Returns (time_str, is_recent) for the latest file in the input directory."""
    input_dir = Path("input_file") / date_str
    if not input_dir.exists():
        return "No data", False
    
    files = list(input_dir.glob("*.csv")) + list(input_dir.glob("*.xlsx"))
    if not files:
        return "No data", False
    
    # Sort by modification time
    latest_file = max(files, key=lambda p: p.stat().st_mtime)
    mtime = datetime.fromtimestamp(latest_file.stat().st_mtime)
    
    time_label = mtime.strftime("%I:%M %p")
    # Mark as recent if updated in the last 10 minutes
    is_recent = (datetime.now() - mtime) < timedelta(minutes=10)
    
    return time_label, is_recent
