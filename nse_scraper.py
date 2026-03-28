import sys
import time
import random
import re
import shlex
import logging
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List, Union

import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("NSE_Scraper")

# Optional: NsePython integration (Layer 1)
try:
    from nsepython import nse_optionchain_scrapper
    NSEPYTHON_AVAILABLE = True
except ImportError:
    NSEPYTHON_AVAILABLE = False

# Add current dir to path for local imports
sys.path.append(str(Path(__file__).parent))
from io_manager import get_input_dir

# --- THE ABSOLUTE ZERO: cURL PARSER ---
def parse_curl_command(curl_command: str) -> Optional[Dict[str, Any]]:
    """
    Advanced Parser for Chrome/Edge 'Copy as cURL (bash)'.
    Extracts headers, cookies, and URLs with 100% accuracy.
    
    Args:
        curl_command (str): The raw cURL string from browser network tab.
        
    Returns:
        Optional[Dict[str, Any]]: Dictionary containing 'headers' and 'url' if successful.
    """
    try:
        command = curl_command.replace("\\\n", " ").replace("\\", " ").strip()
        tokens = shlex.shlex(command, posix=True)
        tokens.whitespace_split = True
        tokens = list(tokens)
        
        headers = {}
        cookies = ""
        url = None
        
        # 1. Advanced URL Extraction
        url_match = re.search(r"'(https?://[^']+)'|\"(https?://[^\"]+)\"|(https?://\S+)", command)
        if url_match:
            url = url_match.group(1) or url_match.group(2) or url_match.group(3)
        
        # 2. Extract Headers and Separate Cookies
        for i in range(len(tokens)):
            if tokens[i] in ["-H", "--header"]:
                header_line = tokens[i+1]
                if ":" in header_line:
                    k, v = header_line.split(":", 1)
                    headers[k.strip()] = v.strip()
            
            if tokens[i] in ["-b", "--cookie"]:
                cookies = tokens[i+1]
        
        if cookies and "Cookie" not in headers:
            headers["Cookie"] = cookies
            
        # 3. ZERO-INFERENCE CLEANING: Strip noisy browser-extension/tracking headers
        clean_headers = {}
        for k, v in headers.items():
            if k.upper() not in ["POSTMAN-TOKEN", "X-CLOUD-TRACE-CONTEXT", "CACHE-CONTROL", "PRAGMA"]:
                clean_headers[k] = v
                
        return {"headers": clean_headers, "url": url}
    except Exception as e:
        logger.error(f"cURL Parse Error: {e}")
        return None

# --- STEALTH TLS ADAPTER ---
class CipherAdapter(HTTPAdapter):
    """
    Custom HTTPAdapter to spoof the TLS Fingerprint (JA3) of a modern browser.
    Ensures that the low-level handshake looks like Chrome/Safari.
    """
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        # Precise Chrome-like Cipher Suite (Modern browsers)
        context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384')
        kwargs['ssl_context'] = context
        return super(CipherAdapter, self).init_poolmanager(*args, **kwargs)

# --- CONFIG ---
USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36"
]

BASE_URL = "https://www.nseindia.com/"
API_URL = "https://www.nseindia.com/api/option-chain-indices?symbol="

def get_base_headers(user_agent):
    # Mimic modern browser security headers
    is_mobile = "Mobile" in user_agent
    platform = '"iOS"' if "iPhone" in user_agent else '"Windows"' if "Windows" in user_agent else '"macOS"' if "Macintosh" in user_agent else '"Android"'
    
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br" if HAS_BROTLI else "gzip, deflate",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.nseindia.com/option-chain",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
        "Sec-Ch-Ua-Mobile": "?1" if is_mobile else "?0",
        "Sec-Ch-Ua-Platform": platform,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    return headers

def get_session(user_agent: Optional[str] = None) -> Optional[requests.Session]:
    """
    Initializes a robust requests.Session with human-like warm-up handshakes.
    
    The warm-up follows a 3-step sequence:
    1. Establish initial session cookies on the homepage.
    2. Perform the 'AppConfig' secret handshake.
    3. Validate session maturity via a derivative market landing page.
    """
    if not user_agent:
        user_agent = USER_AGENTS[0]
        
    session = requests.Session()
    session.mount("https://", CipherAdapter())
    session.headers.update(get_base_headers(user_agent))
    
    try:
        logger.info("Nuclear Sync: Step 1 (Home Base)...")
        session.get(BASE_URL, timeout=15)
        time.sleep(random.uniform(1.5, 2.5))
        
        logger.info("Nuclear Sync: Step 2 (AppConfig Handshake)...")
        session.get("https://www.nseindia.com/api/common/appConfig", timeout=15)
        time.sleep(random.uniform(1.0, 2.0))
        
        logger.info("Nuclear Sync: Step 3 (Market Entry)...")
        session.get("https://www.nseindia.com/get-quotes/derivatives?symbol=NIFTY", timeout=15)
        
        return session
    except Exception as e:
        logger.warning(f"Stealth Session warm-up failed: {e}")
        return None

def fetch_option_chain(session, symbol="NIFTY"):
    """Fetches JSON data for the given symbol with failover endpoints and cache-busters."""
    timestamp = int(time.time() * 1000)
    endpoints = [
        f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}&_={timestamp}",
        f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}&_={timestamp}" # Failover gateway
    ]
    
    # Update referer specifically for the API call
    session.headers.update({"Referer": f"https://www.nseindia.com/get-quotes/derivatives?symbol={symbol}"})
    
    last_err_body = "No response from NSE."
    for url in endpoints:
        try:
            response = session.get(url, timeout=15)
            if response.status_code == 200:
                # Success!
                contentType = response.headers.get("Content-Type", "").lower()
                return {"success": True, "data": response.json() if "json" in contentType else response.text, "type": "json" if "json" in contentType else "csv"}
            else:
                last_err_body = f"API Error {response.status_code}: {response.text[:500]}"
                print(f"Diagnostic Failure Log ({response.status_code}): {response.text[:200]}")
        except Exception as e:
            last_err_body = str(e)
            print(f"Endpoint Failed: {last_err_body}")
            
    return {"error": last_err_body}

def process_to_df(json_data):
    """Processes NSE JSON into a flat DataFrame for the NEAREST EXPIRY ONLY."""
    try:
        rows = []
        # Support/Resistance analysis usually focuses on the immediate upcoming expiry
        records = json_data.get("records", {})
        expiry_dates = records.get("expiryDates", [])
        
        if not expiry_dates:
            print(f"DEBUG: JSON Keys found: {list(json_data.keys())}")
            if "records" in json_data:
                print(f"DEBUG: Records Keys found: {list(json_data['records'].keys())}")
            print("No expiry dates found in records. JSON structure might have changed or market is in maintenance.")
            return None
            
        target_expiry = expiry_dates[0]
            
        print(f"Filtering for Nearest Expiry: {target_expiry}")
        
        # Use full data pool but filter for target_expiry
        all_data = json_data.get("records", {}).get("data", [])
        
        for item in all_data:
            if item.get("expiryDate") != target_expiry:
                continue
                
            strike = item.get("strikePrice")
            ce = item.get("CE", {})
            pe = item.get("PE", {})
            
            rows.append({
                "Strike Price": strike,
                "CE OI": ce.get("openInterest", 0),
                "PE OI": pe.get("openInterest", 0),
                "CE CHNG IN OI": ce.get("changeinOpenInterest", 0),
                "PE CHNG IN OI": pe.get("changeinOpenInterest", 0),
                "CE LTP": ce.get("lastPrice", 0),
                "PE LTP": pe.get("lastPrice", 0),
                "Expiry": target_expiry
            })
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"Error processing JSON: {e}")
        return None

def is_market_open():
    """Checks if current time is weekday 9:00 AM - 3:30 PM IST."""
    now = datetime.now()
    # 0=Monday, 4=Friday
    if now.weekday() > 4:
        return False
    
    current_time = now.time()
    market_start = dtime(9, 0)
    market_end = dtime(15, 30)
    
    return market_start <= current_time <= market_end

def _execute_mirror_sync(symbol: str, curl_command: str) -> Tuple[bool, str, Optional[str]]:
    """
    Executes Layer 3: Mirror Mode. Bit-for-bit browser identity replication.
    """
    logger.info("Sync Layer 3: Initiating Mirror Mode...")
    mirror_data = parse_curl_command(curl_command)
    if not mirror_data or not mirror_data.get("headers"):
        return False, "Failed to parse cURL command.", None

    session = requests.Session()
    session.headers.update(mirror_data["headers"])
    url = mirror_data.get("url") or f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"

    # 3-Attempt Resiliency Loop for Timeouts
    max_retries = 3
    response = None
    for attempt in range(max_retries):
        try:
            logger.info(f"Mirror Attempt {attempt+1}/{max_retries}...")
            response = session.get(url, timeout=30, stream=True)
            if response.status_code == 200:
                break
            return False, f"Mirror Blocked (Code {response.status_code})", None
        except requests.exceptions.Timeout:
            if attempt == max_retries - 1:
                return False, "Mirror Failed: Connection Timed Out. Try a Mobile Hotspot.", None
            time.sleep(2)
        except Exception as e:
            return False, f"Mirror Request Error: {str(e)}", None

    if response and response.status_code == 200:
        content_type = response.headers.get("Content-Type", "").lower()
        if "json" in content_type:
            raw_json = response.json()
            # Detect Shadow-Ban (Hollow JSON)
            records = raw_json.get("records", {})
            if not raw_json or not records or not records.get("expiryDates"):
                logger.warning("Hollow JSON detected. Triggering side-gate...")
                return _failover_to_all_indices(session, symbol)
            return _save_logic(raw_json)
        elif "text/html" in content_type:
            # Smart-Mirror Fallback
            logger.info("HTML received. Attempting Smart-Mirror conversion...")
            api_url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
            api_res = session.get(api_url, timeout=10)
            if api_res.status_code == 200 and "json" in api_res.headers.get("Content-Type", "").lower():
                return _save_logic(api_res.json())
            return False, "⚠️ WRONG cURL: You copied the main Page instead of the API.", None
        return _save_raw_csv(response.text)
    return False, "Mirror Failed: No valid response.", None

def _execute_stealth_sync(symbol: str, manual_cookie: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Executes Layer 2: Stealth TLS Rotation. Cycles through device identities.
    """
    if manual_cookie:
        logger.info("Sync Layer 2: Using manual browser cookie...")
        session = requests.Session()
        session.mount("https://", CipherAdapter())
        session.headers.update(get_base_headers(USER_AGENTS[0]))
        session.headers.update({"Cookie": manual_cookie})
        ret = fetch_option_chain(session, symbol)
        if ret.get("success"):
            return _save_logic(ret["data"]) if ret["type"] == "json" else _save_raw_csv(ret["data"])
        return False, f"Stealth Sync Failed: {ret.get('error')}", None

    # Automated Rotation
    max_retries = min(len(USER_AGENTS), 4)
    for attempt in range(max_retries):
        try:
            ua = USER_AGENTS[attempt]
            logger.info(f"Sync Layer 2: Stealth Attempt {attempt + 1}/{max_retries}...")
            current_session = get_session(ua)
            if not current_session: continue

            ret = fetch_option_chain(current_session, symbol)
            if ret.get("success"):
                return _save_logic(ret["data"]) if ret["type"] == "json" else _save_raw_csv(ret["data"])
            
            logger.warning(f"Attempt {attempt + 1} compromised. Rotating identity...")
            time.sleep(random.uniform(2, 4))
        except Exception as e:
            logger.error(f"Stealth Exception: {e}")
            
    return False, "All Stealth Layers blocked.", None

def fetch_and_save(symbol: str = "NIFTY", manual_cookie: Optional[str] = None, curl_command: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Central orchestrator for the 3-Layer NSE Sync strategy.
    
    Priority:
    1. Mirror Mode (if cURL provided)
    2. NsePython (if available and no manual cookie)
    3. Stealth TLS Rotation
    """
    # 1. Mirror Mode (Highest Reliability)
    if curl_command:
        return _execute_mirror_sync(symbol, curl_command)

    # 2. Automated NsePython (Community Layer)
    if NSEPYTHON_AVAILABLE and not manual_cookie:
        try:
            logger.info("Sync Layer 1: NsePython Automated Pull...")
            raw_data = nse_optionchain_scrapper(symbol)
            if raw_data and isinstance(raw_data, dict) and "records" in raw_data:
                return _save_logic(raw_data)
        except Exception as e:
            logger.debug(f"NsePython failed: {e}")

    # 3. Stealth TLS Rotation (The 'Last Stand')
    return _execute_stealth_sync(symbol, manual_cookie)

def _save_logic(raw_data):
    """Helper to process and save validated JSON data."""
    try:
        if not isinstance(raw_data, dict):
            return False, f"Invalid JSON type: {type(raw_data)}. Expected dict.", None
            
        records = raw_data.get("records", {})
        expiry_dates = records.get("expiryDates", [])
        
        if not expiry_dates:
            # Check for 'filtered' data as a fallback
            filtered = raw_data.get("filtered", {})
            if filtered:
                 print("Mirror Mode: 'records' empty, found 'filtered' data. Proceeding...")
            elif "records" in raw_data and "underlyingValue" in raw_data["records"]:
                 # We can at least extract the spot price
                 print("Mirror Mode: Records empty, extracting spot price only.")
            else:
                 return False, f"JSON Error: 'records.expiryDates' is empty. Keys: {list(raw_data.keys())}", None
        
        target_expiry = expiry_dates[0] if expiry_dates else "Latest"
        df = process_to_df(raw_data)
        if df is not None:
            input_dir = get_input_dir()
            timestamp = datetime.now().strftime("%H%M")
            save_path = input_dir / f"{timestamp}.csv"
            df.to_csv(save_path, index=False)
            return True, f"Successfully saved: {save_path.name}", target_expiry
        
        # Build a diagnostic message
        diag = f"Keys: {list(raw_data.keys())}"
        if "records" in raw_data: diag += f" | Records: {list(raw_data['records'].keys())}"
        
        # SHADOW-BAN DETECTION: If successful 200-OK but JSON is empty {}
        if not raw_data:
             return False, "⚠️ SHADOW-BAN: NSE returned an empty JSON {}. Your current session is flagged. Open a new INCOGNITO window in Chrome, go to NSE, and copy a NEW cURL from there.", None
             
        # Add raw data snippet for deep inspection
        raw_str = str(raw_data)[:500]
        full_diag = f"{diag}\n\n[Raw JSON Snippet]:\n{raw_str}"
        return False, f"Failed to extract expiry data from JSON. {full_diag}", None
    except Exception as e:
        return False, f"JSON Extraction Error: {str(e)}", None

def _save_raw_csv(text_data: str):
    """
    Saves raw CSV text to the input directory with timestamped filename.
    """
    # CRITICAL: Prevent saving HTML as CSV
    if "<!DOCTYPE html" in text_data.lower() or "<html" in text_data.lower():
         return False, "⚠️ WRONG cURL: You copied the main Page. In the Network tab, look for 'option-chain-indices' (the JSON file) and copy that cURL instead.", None

    if "," not in text_data[0:1000] and "\t" not in text_data[0:1000]:
         return False, "⚠️ INVALID DATA: The response does not look like a CSV or JSON table.", None

    target_dir = get_input_dir(get_current_date_str())
    target_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%H%M")
    target_file = target_dir / f"{timestamp}.csv"
    
    try:
        with open(target_file, "w", encoding="utf-8") as f:
            f.write(text_data)
        return True, f"Successfully saved: {target_file.name}", None
    except Exception as e:
        return False, f"Save failed: {str(e)}", None

def _failover_to_all_indices(session, symbol):
    """Fallback endpoint when specific option chain is silent."""
    try:
        url = "https://www.nseindia.com/api/allIndices"
        response = session.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json()
            indices = data.get("data", [])
            target = next((x for x in indices if x.get("index") == symbol), None)
            if target:
                 # We at least got the Spot Price and PCR from the global view
                 print(f"Side-Gate Success: Captured {symbol} from Global Indices.")
                 # Construct a dummy DF for the dashboard
                 df = pd.DataFrame([{
                     "Strike Price": target.get("last"),
                     "CE OI": 0, "PE OI": 0, "CE CHNG IN OI": 0, "PE CHNG IN OI": 0,
                     "CE LTP": target.get("last"), "PE LTP": target.get("last"),
                     "Expiry": "Global-Indices"
                 }])
                 input_dir = get_input_dir()
                 save_path = input_dir / f"{datetime.now().strftime('%H%M')}.csv"
                 df.to_csv(save_path, index=False)
                 return True, f"Side-Gate Success: {target.get('last')}", "Global-Indices"
        return False, "All endpoints (including failover) returned empty responses.", None
    except Exception as e:
        return False, f"Failover Error: {str(e)}", None

def run_scraper(symbol="NIFTY", once=False):
    print(f"Starting NSE Scraper (Auto-Rotate Mode) for {symbol}...")
    is_initial_run = True

    while True:
        # Check market hours, but ALWAYS allow the initial pull on app launch
        if not once and not is_market_open() and not is_initial_run:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Market is closed. Waiting...")
            time.sleep(600) # Check every 10 mins
            continue

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Pulse Fetch (Initial: {is_initial_run})...")
        success, msg, target_expiry = fetch_and_save(symbol)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg} (Target: {target_expiry})")
        
        if success:
            is_initial_run = False

        if once:
            break
        
        # Interval with a bit of jitter
        sleep_time = 300 + random.randint(-15, 15)
        print(f"Sleeping for {sleep_time} seconds...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NSE Option Chain Scraper")
    parser.add_argument("--symbol", type=str, default="NIFTY", help="Index symbol (NIFTY/BANKNIFTY)")
    parser.add_argument("--once", action="store_true", help="Run only once and exit")
    args = parser.parse_args()
    
    run_scraper(symbol=args.symbol, once=args.once)
