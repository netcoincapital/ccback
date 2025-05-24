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

### Blockchain Transaction API

The system now uses RESTful blockchain-specific endpoints for transaction operations:

#### Prepare Transaction

```
POST /api/{blockchain}/prepare
```

Prepares a transaction for the specified blockchain. Replace `{blockchain}` with the blockchain identifier (e.g., `ethereum`, `bitcoin`, `bsc`).

Request body:
```json
{
  "sender_address": "0x...",
  "recipient_address": "0x...",
  "amount": "0.01",
  "smart_contract_address": "0x..." // optional, for token transfers
}
```

Response:
```json
{
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "details": {
    "amount": "0.01",
    "blockchain": "Ethereum",
    "estimated_fee": "0.0021",
    "explorer_url": "https://etherscan.io/tx/...",
    "recipient": "0x...",
    "sender": "0x...",
    "sender_balance_after": "0.9879",
    "sender_balance_before": "1.0"
  },
  "expires_at": "2023-07-22T15:30:00.000Z",
  "message": "Transaction prepared successfully",
  "success": true
}
```

#### Confirm Transaction

```
POST /api/{blockchain}/confirm
```

Confirms and sends a prepared transaction. Replace `{blockchain}` with the blockchain identifier.

Request body:
```json
{
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "private_key": "0x..."
}
```

Response:
```json
{
  "success": true,
  "transaction_hash": "0x...",
  "status": "pending",
  "message": "Transaction sent successfully"
}
```

#### Get Blockchain Information

```
GET /api/blockchains
```

Returns information about all supported blockchains.

Response:
```json
{
  "success": true,
  "blockchains": [
    {
      "name": "ethereum",
      "display_name": "Ethereum",
      "currency_symbol": "ETH",
      "chain_id": 1,
      "decimal_places": 18,
      "explorer_url": "https://etherscan.io"
    },
    {
      "name": "bsc",
      "display_name": "Binance Smart Chain",
      "currency_symbol": "BNB",
      "chain_id": 56,
      "decimal_places": 18,
      "explorer_url": "https://bscscan.com"
    },
    // other blockchains...
  ]
}
```

#### Get Supported Blockchains

```
GET /api/test
```

Returns a simple list of supported blockchain identifiers.

Response:
```json
{
  "success": true,
  "message": "Blockchain API is working",
  "available_blockchains": [
    "ethereum",
    "bsc",
    "bitcoin",
    "tron",
    // other blockchains...
  ]
}
```

### Legacy API Endpoints (Backward Compatibility)

For backward compatibility, the following endpoints are still available but will be redirected to the blockchain-specific endpoints:

```
POST /send/prepare
POST /send/confirm
```

These endpoints require a `blockchain` parameter in the request body to determine which blockchain-specific endpoint to use.

## JavaScript Client Library

A JavaScript client library is provided for easy integration:

```javascript
// Initialize the client
const api = new BlockchainApi();

// Prepare a transaction
const txDetails = await api.prepareTransaction('ethereum', {
  sender_address: '0x...',
  recipient_address: '0x...',
  amount: '0.01'
});

// Confirm a transaction
const result = await api.confirmTransaction('ethereum', {
  transaction_id: txDetails.transaction_id,
  private_key: '0x...'
});

// Get supported blockchains
const blockchains = await api.getSupportedBlockchains();

// Get blockchain details
const details = await api.getBlockchainDetails();

// Get explorer URL for a transaction
const url = await api.getExplorerUrl('ethereum', '0x...');
```

## Adding New Blockchain Support

To add support for a new blockchain:

1. Create a new service class in `services/blockchains/` that extends `BaseBlockchainService`
2. Implement all required methods in the service class
3. Add the blockchain configuration to `utils/blockchain_config.json`
4. Register the service in `utils/blockchain_service_factory.py`

The system will automatically generate API endpoints for the new blockchain.

## Environment Variables

The following environment variables are required:

- `TATUM_API_KEY`: API key for Tatum
- `SECRET_KEY`: Secret key for Flask sessions
- `DATABASE_URL`: PostgreSQL database URL
- `REDIS_URL`: Redis URL for transaction storage
- `INFURA_PROJECT_ID`: Infura project ID for Ethereum and EVM-compatible chains

## License

Proprietary - All rights reserved 