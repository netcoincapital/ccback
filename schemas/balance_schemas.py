from pydantic import BaseModel, Field
from typing import Dict, Optional, Any, List

class UserBalanceRequest(BaseModel):
    """Schema for user balance request"""
    UserID: str = Field(
        ..., 
        description="Unique identifier for the user",
        example="123e4567-e89b-12d3-a456-426614174000"
    )
    CurrencyName: List[str] = Field(
        ...,
        description="List of currency names to fetch balances for",
        example=["Bitcoin", "Ethereum"]
    )
    Blockchain: Optional[Dict[str, str]] = Field(
        None,
        description="Mapping of currency names to blockchain names",
        example={"Shiba Inu": "Ethereum", "Netcoincapital": "Ethereum"}
    )

class TokenBalanceItem(BaseModel):
    """Schema for token balance item"""
    balance: str = Field(
        ..., 
        description="Token balance amount",
        example="0.0123456789"
    )
    currency_name: str = Field(
        ..., 
        description="Name of the currency",
        example="Bitcoin"
    )
    symbol: str = Field(
        ..., 
        description="Symbol of the currency",
        example="BTC"
    )
    blockchain: Optional[str] = Field(
        None, 
        description="Name of the blockchain",
        example="Bitcoin"
    )
    is_token: bool = Field(
        ..., 
        description="Whether this is a token or a native currency",
        example=False
    )

class UserBalanceResponse(BaseModel):
    """Schema for user balance response"""
    UserID: str = Field(
        ..., 
        description="Unique identifier for the user",
        example="123e4567-e89b-12d3-a456-426614174000"
    )
    Tokens: Dict[str, TokenBalanceItem] = Field(
        ..., 
        description="Dictionary of token balances by currency ID",
        example={
            "BTC": {
                "balance": "0.0123456789",
                "currency_name": "Bitcoin",
                "symbol": "BTC",
                "blockchain": "Bitcoin",
                "is_token": False
            },
            "ETH": {
                "balance": "0.5678901234",
                "currency_name": "Ethereum",
                "symbol": "ETH",
                "blockchain": "Ethereum",
                "is_token": False
            }
        }
    )
    success: bool = Field(
        True,
        description="Whether the request was successful",
        example=True
    )

class BalanceUpdateEvent(BaseModel):
    """Schema for balance update event"""
    UserID: str = Field(
        ..., 
        description="Unique identifier for the user",
        example="123e4567-e89b-12d3-a456-426614174000"
    )
    Tokens: Dict[str, TokenBalanceItem] = Field(
        ..., 
        description="Dictionary of token balances by currency ID"
    )
    event_type: str = Field(
        "balance_update",
        description="Type of event",
        example="balance_update"
    )
    timestamp: int = Field(
        ...,
        description="Unix timestamp of the event",
        example=1625097600
    )

class BalancePollingStatusResponse(BaseModel):
    """Schema for balance polling status response"""
    running: bool = Field(
        ...,
        description="Whether the balance polling service is running",
        example=True
    )
    success: bool = Field(
        True,
        description="Whether the request was successful",
        example=True
    ) 