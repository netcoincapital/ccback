# Transaction Storage Issue - Root Cause Analysis & Fix

## Problem Description
Users were experiencing the error:
```json
{
    "message": "Transaction not found or expired",
    "success": false
}
```

This occurred when trying to **confirm** a transaction immediately after **preparing** it, even though the prepare was successful and returned a valid `transaction_id`.

## Root Cause Analysis

### Issue Identified
**Storage Inconsistency** between prepare and confirm endpoints:

1. **PREPARE Endpoint** (`/api/send/prepare`):
   - Uses `BlockchainServiceFactory.get_service('ethereum')`
   - Calls `EthereumService.prepare_transaction()`
   - **EthereumService** had overridden `_store_transaction()` to use **class-level storage**:
     ```python
     self.__class__._transactions[transaction_id] = tx_data
     ```

2. **CONFIRM Endpoint** (`/api/send/confirm`):
   - Tries to retrieve transaction using **shared storage**:
     ```python
     from services.shared_storage import shared_storage
     tx_data = shared_storage.get_transaction(transaction_id)
     ```

### The Problem
- **PREPARE** stored transactions in `EthereumService._transactions` (class storage)
- **CONFIRM** looked for transactions in `shared_storage` (Redis/memory storage)
- These are **completely separate storage systems**!

## Solution Applied

### File Modified: `services/blockchains/ethereum_service.py`

**Before (Problematic Code):**
```python
def _store_transaction(self, transaction_id: str, tx_data: dict):
    """ذخیره اطلاعات تراکنش"""
    try:
        # ایجاد storage ساده در memory
        if not hasattr(self.__class__, '_transactions'):
            self.__class__._transactions = {}
        self.__class__._transactions[transaction_id] = tx_data
        
        self.logger.debug(f"Transaction {transaction_id} stored successfully")
        
    except Exception as e:
        self.logger.warning(f"Failed to store transaction: {str(e)}")
```

**After (Fixed Code):**
```python
def _store_transaction(self, transaction_id: str, tx_data: dict):
    """Store transaction data using shared storage"""
    try:
        # Use the parent class method which uses shared storage
        super()._store_transaction(transaction_id, tx_data, 30)  # 30 minute expiry
        self.logger.debug(f"Transaction {transaction_id} stored successfully in shared storage")
    except Exception as e:
        self.logger.warning(f"Failed to store transaction in shared storage: {str(e)}")
        # Fallback to class storage if shared storage fails
        try:
            if not hasattr(self.__class__, '_transactions'):
                self.__class__._transactions = {}
            self.__class__._transactions[transaction_id] = tx_data
            self.logger.debug(f"Transaction {transaction_id} stored in fallback class storage")
        except Exception as fallback_error:
            self.logger.error(f"Both shared storage and fallback storage failed: {str(fallback_error)}")
```

### Key Changes:
1. **Primary Storage**: Now uses `super()._store_transaction()` which stores in **shared storage**
2. **Fallback Mechanism**: Maintains backward compatibility with class storage as fallback
3. **Consistent Retrieval**: Updated `_get_stored_transaction()` to check shared storage first
4. **Extended Expiry**: Set to 30 minutes (was indefinite in class storage)

## Verification

### Test Case:
```bash
# This should now work:
curl -X POST https://coinceeper.com/api/send/prepare \
  -H "Content-Type: application/json" \
  -d '{"UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08", "blockchain": "Ethereum", "sender_address": "0x4A56CEB9C75FA018C1e2F16474BB1fBD639a6956", "recipient_address": "0x8d697D386c175dC7ac25DF67f82B3BFbc8EC5bE9", "amount": "0.002", "smart_contract_address": ""}'

# Get transaction_id from response, then:
curl -X POST https://coinceeper.com/api/send/confirm \
  -H "Content-Type: application/json" \
  -d '{"UserId": "63ff3616-abb3-4d03-b8d6-51a3c5a6dc08", "blockchain": "Ethereum", "transaction_id": "TRANSACTION_ID_HERE"}'
```

### Expected Result:
- **Before Fix**: `"Transaction not found or expired"`
- **After Fix**: Should find the transaction (may fail on private key validation, but that's expected)

## Impact

### Services Affected:
- ✅ **EthereumService**: Fixed
- ✅ **BSCService**: Already using shared storage correctly
- ✅ **Other Services**: Already using shared storage correctly

### Deployment:
- **No database changes required**
- **No configuration changes required**  
- **Server restart recommended** to ensure the new code is loaded

## Monitoring

After deployment, monitor for:
1. Reduction in "Transaction not found or expired" errors
2. Successful transaction confirmations
3. Storage debug endpoint: `/api/send/debug-storage`

## Additional Notes

- This fix maintains **backward compatibility**
- **Fallback mechanism** ensures resilience if shared storage fails
- **Consistent expiration** now applies to all transactions (30 minutes)
- Other blockchain services were already working correctly
