from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any

# Wallet Generation Schemas
class WalletGenerationRequest(BaseModel):
    """Schema for wallet generation request"""
    WalletName: str = Field(
        ..., 
        description="Name of the wallet", 
        min_length=3, 
        max_length=50,
        example="My Main Wallet"
    )

class WalletGenerationResponse(BaseModel):
    """Schema for wallet generation response"""
    task_id: str = Field(
        ..., 
        description="Task ID for tracking wallet generation",
        example="123e4567-e89b-12d3-a456-426614174000"
    )
    status: str = Field(
        ..., 
        description="Status of the wallet generation",
        example="processing"
    )
    message: str = Field(
        ..., 
        description="Status message",
        example="Wallet generation in progress"
    )
    success: bool = Field(
        ...,
        description="Whether the request was successful",
        example=True
    )

class WalletGenerationStatusResponse(BaseModel):
    """Schema for wallet generation status response"""
    status: str = Field(
        ..., 
        description="Current status of wallet generation",
        example="completed"
    )
    result: Optional[Dict[str, Any]] = Field(
        None,
        description="Result data if generation is complete"
    )
    success: bool = Field(
        ...,
        description="Whether the request was successful",
        example=True
    )

class WalletGenerationSyncResponse(BaseModel):
    """Schema for synchronous wallet generation response"""
    success: bool = Field(..., description="Whether the request was successful")
    UserID: Optional[str] = Field(None, description="The ID of the user who owns the wallet", example="123e4567-e89b-12d3-a456-426614174000")
    WalletID: Optional[str] = Field(None, description="The ID of the generated wallet", example="123e4567-e89b-12d3-a456-426614174000")
    Mnemonic: Optional[str] = Field(None, description="The mnemonic phrase for the wallet", example="word1 word2 word3 word4 word5 word6 word7 word8 word9 word10 word11 word12")
    message: Optional[str] = Field(None, description="A message about the wallet generation status")

# Wallet Import Schemas
class WalletImportRequest(BaseModel):
    """Schema for wallet import request"""
    mnemonic: str = Field(
        ..., 
        description="Mnemonic recovery phrase", 
        min_length=12, 
        max_length=1000,
        example="abandon ability able about above absent absorb abstract absurd abuse access accident"
    )

    @validator('mnemonic')
    def validate_mnemonic_words(cls, v):
        words = v.split()
        if len(words) not in [12, 18, 24]:
            raise ValueError("Mnemonic must contain 12, 18, or 24 words")
        return v

class WalletImportResponse(BaseModel):
    """Schema for wallet import response"""
    WalletID: str = Field(
        ..., 
        description="Unique identifier for the wallet",
        example="123e4567-e89b-12d3-a456-426614174000"
    )
    Addresses: Dict[str, str] = Field(
        ..., 
        description="Imported addresses for each blockchain",
        example={
            "Bitcoin": "bc1q5c9vlt5uq9u4njr5j3spdcmwgaazr6uhv5xrm0",
            "Ethereum": "0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
        }
    )
    success: bool = Field(
        ...,
        description="Whether the request was successful",
        example=True
    )

class MnemonicValidationRequest(BaseModel):
    """Schema for mnemonic validation request"""
    mnemonic: str = Field(
        ..., 
        description="Mnemonic recovery phrase to validate", 
        min_length=12, 
        max_length=1000,
        example="abandon ability able about above absent absorb abstract absurd abuse access accident"
    )

class MnemonicValidationResponse(BaseModel):
    """Schema for mnemonic validation response"""
    is_valid: bool = Field(
        ..., 
        description="Whether the mnemonic is valid",
        example=True
    )
    word_count: int = Field(
        ..., 
        description="Number of words in the mnemonic",
        example=12
    )
    success: bool = Field(
        ...,
        description="Whether the request was successful",
        example=True
    )

# Error Response Schema
class ErrorResponse(BaseModel):
    """Schema for error responses"""
    success: bool = Field(
        False,
        description="Always false for error responses",
        example=False
    )
    error_type: str = Field(
        ...,
        description="Type of error that occurred",
        example="validation_error"
    )
    message: str = Field(
        ...,
        description="Error message",
        example="Invalid input data"
    )

# Currency Schemas
class CurrencyListRequest(BaseModel):
    """Schema for currency list request"""
    page: int = Field(
        1, 
        description="Page number for pagination",
        ge=1,
        example=1
    )
    per_page: int = Field(
        10, 
        description="Number of items per page",
        ge=1,
        le=100,
        example=10
    )

class CurrencyItem(BaseModel):
    """Schema for currency item"""
    CurrencyID: str = Field(
        ..., 
        description="Unique identifier for the currency",
        example="BTC"
    )
    CurrencyName: str = Field(
        ..., 
        description="Name of the currency",
        example="Bitcoin"
    )
    Symbol: str = Field(
        ..., 
        description="Symbol of the currency",
        example="BTC"
    )
    Icon: str = Field(
        ..., 
        description="URL to the currency icon",
        example="https://example.com/icons/btc.png"
    )
    BlockchainID: int = Field(
        ..., 
        description="ID of the blockchain this currency belongs to",
        example=1
    )
    IsToken: bool = Field(
        ..., 
        description="Whether this currency is a token",
        example=False
    )
    SmartContractAddress: Optional[str] = Field(
        None, 
        description="Smart contract address for tokens",
        example="0x2170ed0880ac9a755fd29b2688956bd959f933f8"
    )

class CurrencyListResponse(BaseModel):
    """Schema for currency list response"""
    currencies: List[CurrencyItem] = Field(
        ..., 
        description="List of currencies",
        example=[{
            "CurrencyID": "BTC",
            "CurrencyName": "Bitcoin",
            "Symbol": "BTC",
            "Icon": "https://example.com/icons/btc.png",
            "BlockchainID": 1,
            "IsToken": False,
            "SmartContractAddress": None
        }]
    )
    success: bool = Field(
        True, 
        description="Whether the request was successful",
        example=True
    )

class CurrencyPriceRequest(BaseModel):
    """Schema for currency price request"""
    UserID: str = Field(
        ..., 
        description="User ID",
        example="123e4567-e89b-12d3-a456-426614174000"
    )
    CurrencyID: List[str] = Field(
        ..., 
        description="List of currency IDs to get prices for",
        example=["BTC", "ETH", "BNB"]
    )
    FiatCurrencies: List[str] = Field(
        ["USD"], 
        description="List of fiat currencies to get prices in",
        example=["USD", "EUR", "GBP"]
    )

class CurrencyPriceItem(BaseModel):
    """Schema for currency price item"""
    price: str = Field(
        ..., 
        description="Formatted price string",
        example="45,123.45"
    )
    change_24h: str = Field(
        ..., 
        description="24-hour price change percentage",
        example="+2.34%"
    )

class CurrencyPriceResponse(BaseModel):
    """Schema for currency price response"""
    prices: Dict[str, Dict[str, CurrencyPriceItem]] = Field(
        ..., 
        description="Prices by currency symbol and fiat currency",
        example={
            "BTC": {
                "USD": {
                    "price": "45,123.45",
                    "change_24h": "+2.34%"
                },
                "EUR": {
                    "price": "41,234.56",
                    "change_24h": "+2.45%"
                }
            }
        }
    )
    success: bool = Field(
        True, 
        description="Whether the request was successful",
        example=True
    )

class CurrencyUpdateResponse(BaseModel):
    """Schema for currency update response"""
    updated_prices: Dict[str, Any] = Field(
        ..., 
        description="Information about the updated prices",
        example={
            "status": "success",
            "message": "Prices updated"
        }
    )
    success: bool = Field(
        True, 
        description="Whether the request was successful",
        example=True
    )

# PhraseKey Schemas
class PhraseKeyRequest(BaseModel):
    """Schema for phrase key request"""
    UserID: str = Field(
        ..., 
        description="User ID",
        example="123e4567-e89b-12d3-a456-426614174000"
    )

class PhraseKeyResponse(BaseModel):
    """Schema for phrase key response"""
    phrase_key: str = Field(
        ..., 
        description="Encrypted recovery phrase",
        example="encrypted_phrase_key_data"
    )
    success: bool = Field(
        True, 
        description="Whether the operation was successful",
        example=True
    )

# Transaction Schemas
class ReceiveTransactionRequest(BaseModel):
    """Schema for receive transaction request"""
    UserID: str = Field(
        ..., 
        description="User ID",
        example="123e4567-e89b-12d3-a456-426614174000"
    )
    BlockchainName: str = Field(
        ..., 
        description="Name of the blockchain",
        example="Ethereum"
    )

class TransactionDetails(BaseModel):
    """Schema for transaction details"""
    status: str = Field(
        ..., 
        description="Status of the transaction",
        example="success"
    )
    address: str = Field(
        ..., 
        description="Blockchain address",
        example="0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
    )
    network: str = Field(
        ..., 
        description="Blockchain network",
        example="Ethereum"
    )

class ReceiveTransactionResponse(BaseModel):
    """Schema for receive transaction response"""
    transaction: TransactionDetails = Field(
        ..., 
        description="Transaction details"
    )
    success: bool = Field(
        True, 
        description="Whether the operation was successful",
        example=True
    )

# GasFee Schemas
class GasFeeResponse(BaseModel):
    """Schema for gas fee response"""
    gas_fee: Dict[str, Any] = Field(
        ..., 
        description="Gas fee information",
        example={"gas_fee": 45.6}
    )
    success: bool = Field(
        True, 
        description="Whether the operation was successful",
        example=True
    ) 