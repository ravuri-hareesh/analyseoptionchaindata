import sys
import time
import random
import logging
import requests
import re
import json
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
import pandas as pd
from nsepython import nse_optionchain_scrapper

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("NSE_Scraper")

# Add project root to path
sys.path.append(str(Path(__file__).parent))
from data_manager import get_input_dir, normalize_date_str, get_current_date_str

# --- SESSION MGMT ---
session = requests.Session()
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

def init_nse_session():
    """Initializes cookies by visiting the NSE homepage."""
    global session
    url = "https://www.nseindia.com/"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        session.get(url, headers=headers, timeout=10)
        logger.info("NSE Session Initialized (Cookies set).")
        return True
    except Exception as e:
        logger.error(f"Failed to init NSE session: {e}")
        return False

def parse_curl_headers(curl_command: str) -> Dict[str, str]:
    """Extracts headers and cookies from a cURL command string."""
    headers = {}
    matches = re.findall(r'-(?:H|-header)\s+[\'"]?([^\'"]+)[\'"]?', curl_command)
    for m in matches:
        if ":" in m:
            k, v = m.split(":", 1)
            headers[k.strip()] = v.strip()
    return headers

def custom_fetch_option_chain(symbol: str, headers: Optional[Dict] = None) -> Optional[Dict]:
    """Custom fetch using requests session for better control."""
    global session
    base_url = "https://www.nseindia.com/api/option-chain-indices"
    params = {"symbol": symbol}
    
    default_headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/get-quotes/equity?symbol=" + symbol,
        "X-Requested-With": "XMLHttpRequest"
    }
    
    if headers:
        final_headers = {**default_headers, **headers}
    else:
        final_headers = default_headers

    try:
        response = session.get(base_url, params=params, headers=final_headers, timeout=15)
        if response.status_code == 200:
            return response.json()
        else:
            logger.warning(f"Custom fetch failed with status {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Custom fetch exception: {e}")
        return None

def is_market_open():
    """Checks if current time is weekday 9:15 AM - 3:30 PM IST."""
    now = datetime.now()
    if now.weekday() > 4: return False
    current_time = now.time()
    return dtime(9, 15) <= current_time <= dtime(15, 30)

def process_to_df(json_data):
    """Processes NSE JSON into a flat DataFrame for the NEAREST EXPIRY."""
    try:
        records = json_data.get("records", {})
        expiry_dates = records.get("expiryDates", [])
        if not expiry_dates: return None
        
        target_expiry = expiry_dates[0]
        spot_price = json_data.get("underlyingValue") or records.get("underlyingValue") or 0
        
        rows = []
        all_data = records.get("data", [])
        for item in all_data:
            if item.get("expiryDate") == target_expiry:
                ce, pe = item.get("CE", {}), item.get("PE", {})
                rows.append({
                    "Strike Price": item.get("strikePrice"),
                    "CE OI": ce.get("openInterest", 0),
                    "PE OI": pe.get("openInterest", 0),
                    "CE CHNG IN OI": ce.get("changeinOpenInterest", 0),
                    "PE CHNG IN OI": pe.get("changeinOpenInterest", 0),
                    "CE LTP": ce.get("lastPrice", 0),
                    "PE LTP": pe.get("lastPrice", 0),
                    "Expiry": normalize_date_str(target_expiry),
                    "Spot Price": spot_price
                })
        return pd.DataFrame(rows)
    except Exception as e:
        logger.error(f"JSON Processing Error: {e}")
        return None

def fetch_and_save(symbol: str = "NIFTY", curl_command: Optional[str] = None, manual_cookie: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """Primary Auto-Fetch Bridge with Fallbacks and Mirror Mode."""
    try:
        raw_data = None
        
        # 1. Mirror Mode (Highest Priority)
        if curl_command:
            logger.info(f"Using Mirror Mode (cURL Injection) for {symbol}...")
            headers = parse_curl_headers(curl_command)
            raw_data = custom_fetch_option_chain(symbol, headers=headers)
        
        # 2. Manual Cookie Injection
        if not raw_data and manual_cookie:
            logger.info(f"Using Manual Cookie Injection for {symbol}...")
            headers = {"Cookie": manual_cookie}
            raw_data = custom_fetch_option_chain(symbol, headers=headers)
            
        # 3. Standard nsepython (Automated)
        if not raw_data:
            logger.info(f"Syncing {symbol} via nsepython...")
            try:
                raw_data = nse_optionchain_scrapper(symbol)
            except:
                raw_data = None
                
        # 4. Custom Fallback with session init
        if not raw_data or not isinstance(raw_data, dict) or "records" not in raw_data:
            logger.info("Standard fetch failed. Initializing fresh session fallback...")
            if init_nse_session():
                raw_data = custom_fetch_option_chain(symbol)
        
        if not raw_data or not isinstance(raw_data, dict) or "records" not in raw_data:
            return False, "NSE returned invalid or empty data. Mirror Mode required.", None
            
        df = process_to_df(raw_data)
        if df is None or df.empty:
            return False, "Failed to process option chain into DataFrame.", None
            
        target_expiry = df["Expiry"].iloc[0]
        date_str = get_current_date_str()
        
        # 1. Save CSV for traceability
        input_dir = get_input_dir(expiry_date=target_expiry, date_str=date_str)
        timestamp_str = datetime.now().strftime("%H%M")
        save_path = input_dir / f"{timestamp_str}.csv"
        df.to_csv(save_path, index=False)
        
        # 2. Persist to Databases
        try:
            from db_connector import OptEazyDB
            from analysis import compute_pcr, compute_support_resistance
            db = OptEazyDB()
            
            db.save_raw_snapshot(raw_data, target_expiry, datetime.now().isoformat())
            
            spot = df["Spot Price"].iloc[0]
            pcr_bands = {}
            strikes = sorted(df["Strike Price"].unique())
            interval = strikes[1] - strikes[0] if len(strikes) > 1 else 50
            atm_strike = round(spot / interval) * interval
            
            for i in range(1, 6):
                range_pts = spot * (i / 100.0)
                num = max(1, round(range_pts / interval))
                p_res = compute_pcr(df, "Strike Price", "CE OI", "PE OI", 
                                    min_strike=atm_strike - (num * interval), 
                                    max_strike=atm_strike + (num * interval))
                pcr_bands[f"PCR Ranged ({i}%)"] = p_res["ranged_pcr"]
            
            pcr_over = compute_pcr(df, "Strike Price", "CE OI", "PE OI")["overall_pcr"]
            sr = compute_support_resistance(df, "Strike Price", "CE OI", "PE OI")
            
            record = {
                "expiry": target_expiry, "Timestamp": datetime.now(), "Spot": spot, "PCR Overall": pcr_over,
                "Major Support": sr["max_support"].strike, "Major Resistance": sr["max_resistance"].strike,
                "Immediate Support": sr["top_support"][0].strike if sr["top_support"] else 0,
                "Immediate Resistance": sr["top_resistance"][0].strike if sr["top_resistance"] else 0,
                **pcr_bands
            }
            db.save_analysis_record(record)
            db.close()
            logger.info(f"Successfully synced {symbol} (Expiry: {target_expiry}).")
        except Exception as e:
            logger.error(f"DB Sync Error: {e}")
            
        return True, f"Successfully synced: {save_path.name}", target_expiry
    except Exception as e:
        logger.error(f"Fetch Error: {e}")
        return False, str(e), None

def run_scraper(symbol="NIFTY"):
    """Background pulse loop."""
    logger.info(f"Automated Scraper Pulse Started for {symbol}")
    init_nse_session()
    
    while True:
        if is_market_open():
            success, msg, _ = fetch_and_save(symbol)
            logger.info(f"Pulse Result: {msg}")
        else:
            logger.info("Market Closed. Passive mode...")
            
        time.sleep(300 + random.randint(-10, 10))

if __name__ == "__main__":
    fetch_and_save("NIFTY")
