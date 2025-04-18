import requests

url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/map"

headers = {
    "X-CMC_PRO_API_KEY": "bbae831b-bd1b-4949-8945-2b5ab0b9456d"
}

response = requests.get(url, headers=headers)
data = response.json()

for coin in data["data"]:
    if coin["symbol"] == "POL":  # یا "BTC"، "USDT" ...
        print(f'{coin["name"]} - cmcId: {coin["id"]}')