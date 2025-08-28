import requests

TATUM_API_KEY = "t-67e5053a3320cff8fd79c921-0762aaf42dbc4c979d692389"  # Updated to match other parts of the codebase
BASE_URL = "https://api.tatum.io/v3"

def send_coin():
    chain = input("Enter the blockchain (e.g., LTC, BTC, ETH): ").upper()
    private_key = input("Enter the private key: ")
    sender_address = input("Enter the sender address: ")
    recipient_address = input("Enter the recipient address: ")
    amount = input("Enter the amount to send: ")

    payload = {
        "fromAddress": [
            {
                "address": sender_address,
                "privateKey": private_key
            }
        ],
        "to": [
            {
                "address": recipient_address,
                "value": amount
            }
        ]
    }

    url = f"{BASE_URL}/{chain.lower()}/transaction"
    headers = {
        "x-api-key": TATUM_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    print("\nTatum API response:")
    print(response.json())

def send_token():
    chain = input("Enter the blockchain (e.g., ETH, BSC): ").upper()
    private_key = input("Enter the private key: ")
    contract_address = input("Enter the token contract address: ")
    recipient_address = input("Enter the recipient address: ")
    amount = input("Enter the amount to send: ")
    digits = input("Enter token decimals (e.g., 18): ")

    payload = {
        "to": recipient_address,
        "contractAddress": contract_address,
        "digits": int(digits),
        "amount": amount,
        "fromPrivateKey": private_key,
        "chain": chain
    }

    url = f"{BASE_URL}/blockchain/token/transaction"
    headers = {
        "x-api-key": TATUM_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers)
    print("\nTatum API response:")
    print(response.json())

def main():
    print("Select transaction type:")
    print("1. Coin Send")
    print("2. Token Send")
    choice = input("Enter your choice (1 or 2): ")

    if choice == "1":
        send_coin()
    elif choice == "2":
        send_token()
    else:
        print("Invalid selection.")

if __name__ == "__main__":
    main()