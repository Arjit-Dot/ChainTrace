import os
import json
import requests

def fetch_and_cache_blacklisted_wallets(cache_dir="../cache/"):
    """
    Step 3 Adapter: Queries TronGrid for the latest USDT blacklist events 
    and saves the raw responses to the local cache.
    """
    os.makedirs(cache_dir, exist_ok=True)
    
    # Official Tether TRC-20 USDT Contract
    usdt_contract = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    
    # TronGrid Event API Endpoint
    url = f"https://api.trongrid.io/v1/contracts/{usdt_contract}/events"
    
    # Query the 3 most recent blacklisting events
    params = {
        "event_name": "AddedBlackList",
        "limit": 3,
        "order_by": "block_timestamp,desc"
    }
    
    print(f"Querying TronGrid for {usdt_contract}...")
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        events = data.get("data", [])
        
        for idx, event in enumerate(events, 1):
            # Tether's contract uses the parameter '_evilUser' for blacklisted addresses
            wallet_address = event.get("result", {}).get("_evilUser", "UNKNOWN")
            
            # Save the raw TronGrid response to the cache directory
            file_path = os.path.join(cache_dir, f"blacklisted_wallet_{idx}_{wallet_address}.json")
            
            with open(file_path, "w") as f:
                json.dump(event, f, indent=4)
                
            print(f"Saved Wallet {idx} ({wallet_address}) to {file_path}")
    else:
        print(f"Failed to fetch data: {response.status_code} - {response.text}")

if __name__ == "__main__":
    fetch_and_cache_blacklisted_wallets()