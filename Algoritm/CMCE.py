import requests
import csv
import time
import os

# Your CoinMarketCap API Key
API_KEY = "bbae831b-bd1b-4949-8945-2b5ab0b9456d"

# Blockchain platforms mapping
BLOCKCHAINS = {
    #"Ethereum": "ETH",
    #Tron": "TRX",  # فقط Tron برای مثال
    #"Binance Smart Chain": "BNB",
    #"Polygon": "MATIC", 
    #"Arbitrum": "ARB",
    #"Solana": "SOL",
    #"Polkadot": "DOT",
    #"Avalanche": "AVAX",
    #"Ripple": "XRP",
    "Bitcoin": "BTC"
}

# API Endpoints
URL_LISTINGS = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
URL_METADATA = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/info"

# API Request Headers
headers = {
    "Accepts": "application/json",
    "X-CMC_PRO_API_KEY": API_KEY
}

# Ensure output directory exists
os.makedirs("token_images", exist_ok=True)

# List to store all cryptocurrencies
currencies = []


def fetch_tokens_for_blockchain(blockchain_name):
    """ Fetch tokens for a specific blockchain only (اما در اینجا فیلتر نمی‌کنیم) """
    print(f"\n🔄 Fetching tokens (all) for potential {blockchain_name} contracts...\n")
    start = 1
    limit = 4000  # Enforce a strict limit per request
    token_data = {}

    while True:
        params = {
            "start": start,
            "limit": limit,
            "convert": "USD",
            "aux": "platform"
        }

        response = requests.get(URL_LISTINGS, headers=headers, params=params)
        data = response.json()

        # Check if API rate limit exceeded
        if response.status_code == 429:
            print(f"⏳ API rate limit reached! Waiting 60 seconds before retrying {blockchain_name}...")
            time.sleep(60)
            continue

        # Check for errors
        if response.status_code != 200 or "data" not in data:
            print(f"❌ Error fetching token list for {blockchain_name}: {data}")
            break

        batch_size = len(data["data"])
        print(f"✅ Fetched {batch_size} tokens (Batch: {start}-{start + batch_size - 1})")

        # تغییر اصلی ↓
        # -----------------------------
        # اینجا همه توکن‌ها را جمع می‌کنیم و دیگر فیلتری برای پلتفرم نمی‌گذاریم
        for coin in data["data"]:
            token_id = str(coin["id"])
            # ممکن است پلتفرم اصلی چیز دیگری باشد ولی در متادیتا شبکه Tron را داشته باشد
            token_data[token_id] = {
                "name": coin["name"],
                "symbol": coin["symbol"],
                "platform": None
            }
        # -----------------------------

        # Stop pagination when no more data
        if batch_size < limit:
            print(f"✅ Completed fetching tokens for {blockchain_name}.\n")
            break

        start += batch_size  # Move to the next batch

        # Wait to avoid rate limits
        print("⏳ Waiting 10 seconds before the next request to avoid rate limits...")
        time.sleep(10)

    return token_data


def fetch_contract_addresses_and_images(token_data, blockchain_name):
    """ Fetch contract addresses and images for tokens on a specific blockchain """
    print(f"\n🔄 Fetching contract addresses & images for {blockchain_name}...\n")
    batch_size = 50
    token_ids = list(token_data.keys())

    for i in range(0, len(token_ids), batch_size):
        id_batch = ",".join(token_ids[i:i + batch_size])
        params = {"id": id_batch}

        retries = 0
        while retries < 5:
            response = requests.get(URL_METADATA, headers=headers, params=params)
            data = response.json()

            if response.status_code == 429:
                print(f"⏳ Rate limit exceeded! Waiting 30 seconds before retrying {blockchain_name} (batch {i}-{i + batch_size})...")
                time.sleep(30)
                retries += 1
                continue

            if response.status_code != 200 or "data" not in data:
                print(f"❌ Error fetching metadata for {blockchain_name}: {data}")
                return

            break

        for token_id, details in data["data"].items():
            name = details.get("name", "N/A")
            symbol = details.get("symbol", "N/A")
            image_url = details.get("logo", None)
            image_filename = f"{symbol}.png" if image_url else "N/A"

            # اینجا لیست contract_address را بررسی می‌کنیم
            if "contract_address" in details and isinstance(details["contract_address"], list):
                for contract in details["contract_address"]:
                    platform_name = contract.get("platform", {}).get("name", "")
                    contract_address = contract.get("contract_address", "")

                    # تغییر اصلی ↓
                    # -----------------------------
                    # اینجا پلتفرم را کنترل می‌کنیم که اگر Tron بود، در currencies اضافه کنیم
                    if platform_name and "btc" in platform_name.lower():
                        currencies.append({
                            "Name": name,
                            "Symbol": symbol,
                            "Platform": BLOCKCHAINS[blockchain_name],
                            "ContractAddress": contract_address,
                            "Image": image_filename
                        })

                        # اگر تصویر هم داشته باشد، دانلود می‌کنیم
                        if image_url:
                            save_token_image(image_url, image_filename)
                    # -----------------------------

        print(f"✅ Processed {min(i + batch_size, len(token_ids))} tokens for {blockchain_name}...")


def save_token_image(image_url, image_filename):
    """ Downloads and saves token images locally """
    try:
        img_response = requests.get(image_url, stream=True)
        if img_response.status_code == 200:
            with open(f"token_images/{image_filename}", "wb") as img_file:
                for chunk in img_response.iter_content(1024):
                    img_file.write(chunk)
            print(f"🖼️ Saved image: {image_filename}")
        else:
            print(f"❌ Failed to download image: {image_filename}")
    except Exception as e:
        print(f"❌ Error saving image {image_filename}: {e}")


# ** Fetch tokens (all) and then pick Tron tokens from their metadata **
for blockchain in BLOCKCHAINS.keys():
    token_data = fetch_tokens_for_blockchain(blockchain)

    if token_data:
        fetch_contract_addresses_and_images(token_data, blockchain)

    # Save data to CSV file after each blockchain is completed
    csv_filename = "cryptocurrencies.csv"
    
    # اگر فایل وجود ندارد، هدر اضافه می‌کنیم؛ وگرنه صرفاً الحاق (append) می‌کنیم
    file_exists = os.path.isfile(csv_filename)
    with open(csv_filename, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["Name", "Symbol", "Platform", "ContractAddress", "Image"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(currencies)

    print(f"\n✅ Successfully appended {len(currencies)} cryptocurrencies for {blockchain} to {csv_filename}.")

    # break  # اگر خواستید فقط همین یک شبکه انجام شود، uncomment کنید