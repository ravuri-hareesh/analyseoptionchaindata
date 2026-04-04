from nsepython import nse_get_index_quote
import json

def get_nifty_spot():
    try:
        print("Fetching NIFTY 50 Index Quote...")
        # Using nse_get_index_quote which is often more stable for Indices
        data = nse_get_index_quote("NIFTY 50")
        
        if isinstance(data, dict):
            print(f"Debug: Found keys: {list(data.keys())}")
            spot = data.get('last') or data.get('lastPrice') or data.get('underlyingValue')
            if spot:
                print(f"SPOT_RESULT: {spot}")
            else:
                print(f"FAILED: Could not find price in: {json.dumps(data)[:300]}")
        else:
            print(f"FAILED: Received non-dict response: {type(data)}")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    get_nifty_spot()
