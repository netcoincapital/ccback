# IronWallet API

A cryptocurrency wallet management API supporting multiple blockchains.

## Features

- Wallet generation and import
- Support for multiple blockchains (Bitcoin, Ethereum, Tron, Binance, Polygon, Avalanche, Arbitrum, Polkadot, XRP, Solana)
- Transaction signing and sending
- Smart contract interaction
- Currency price tracking

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ironwallet.git
cd ironwallet
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env file with your configuration
```

5. Initialize the database:
```bash
flask db upgrade
```

## Running the Application

Start the application:
```bash
python app.py
```

The API will be available at `https://localhost:5000`.

## API Documentation

The API documentation is available at `https://localhost:5000/api/docs` when the application is running. This interactive documentation allows you to:

- Browse available endpoints
- View request and response schemas
- Test API endpoints directly from the browser

## Development

### Running Tests

Run the test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=.
```

### Worker Processes

Start the wallet generation worker:
```bash
python workers/wallet_worker.py
```

## API Endpoints

### Wallet Management

- `POST /generate-wallet` - Generate a new wallet asynchronously
- `GET /wallet-status/{task_id}` - Check wallet generation status
- `POST /generate-wallet-sync` - Generate a new wallet synchronously (for testing)
- `POST /import_wallet` - Import a wallet using a recovery phrase
- `POST /validate_mnemonic` - Validate a mnemonic phrase without importing

### Transactions

- `POST /Recive` - Receive a transaction
- `GET /gasfee` - Get current gas fees for a blockchain

### Currencies

- `POST /all-currencies` - Get a list of all supported currencies
- `POST /update-prices` - Update currency prices
- `POST /prices` - Get current prices for specified currencies

## License

Proprietary - All rights reserved 