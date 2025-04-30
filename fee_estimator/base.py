"""Base module for fee estimation with common utilities and abstract classes."""

import abc
import time
import logging
from typing import Dict, Any, Optional, Union, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fee_estimator")

class RateLimiter:
    """Simple rate limiter to prevent API abuse."""
    
    def __init__(self, calls_per_second: float = 1.0):
        self.calls_per_second = calls_per_second
        self.last_call_time = 0.0
        
    def wait(self):
        """Wait if needed to respect rate limits."""
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        
        if time_since_last_call < (1.0 / self.calls_per_second):
            sleep_time = (1.0 / self.calls_per_second) - time_since_last_call
            time.sleep(sleep_time)
            
        self.last_call_time = time.time()

class APIClient:
    """Base API client with retry logic and rate limiting."""
    
    def __init__(self, base_url: str, rate_limit: float = 1.0):
        self.base_url = base_url
        self.rate_limiter = RateLimiter(rate_limit)
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """Create a session with retry logic."""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a GET request to the API."""
        self.rate_limiter.wait()
        url = f"{self.base_url}{endpoint}"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a POST request to the API."""
        self.rate_limiter.wait()
        url = f"{self.base_url}{endpoint}"
        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

class FeeEstimator(abc.ABC):
    """Abstract base class for blockchain fee estimators."""
    
    @abc.abstractmethod
    def estimate_native_fee(self, from_address: str, to_address: str, amount: float) -> Dict[str, Any]:
        """
        Estimate fee for native coin transfer.
        
        Args:
            from_address: Source address
            to_address: Destination address
            amount: Amount to transfer in native units
            
        Returns:
            Dict with fee estimation details
        """
        pass
    
    @abc.abstractmethod
    def estimate_token_fee(self, from_address: str, to_address: str, amount: float, token_contract: str) -> Dict[str, Any]:
        """
        Estimate fee for token transfer.
        
        Args:
            from_address: Source address
            to_address: Destination address
            amount: Amount to transfer in token units
            token_contract: Token contract address or identifier
            
        Returns:
            Dict with fee estimation details
        """
        pass
    
    @staticmethod
    def format_fee_response(
        fee: Union[int, float],
        fee_currency: str,
        gas_used: Optional[int] = None,
        gas_price: Optional[Union[int, float]] = None,
        priority_options: Optional[Dict[str, Any]] = None,
        unit: str = "wei",
        usd_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Format the fee response in a standardized way.
        
        Args:
            fee: Base fee amount
            fee_currency: Currency symbol (ETH, BTC, etc.)
            gas_used: Gas units used (for EVM chains)
            gas_price: Gas price (for EVM chains)
            priority_options: Different fee options based on priority
            unit: Unit of the fee amount (wei, satoshi, etc.)
            usd_price: USD equivalent of the fee
            
        Returns:
            Standardized fee response dictionary
        """
        response = {
            "fee": fee,
            "fee_currency": fee_currency,
            "unit": unit,
            "timestamp": int(time.time()),
        }
        
        if gas_used is not None:
            response["gas_used"] = gas_used
            
        if gas_price is not None:
            response["gas_price"] = gas_price
            
        if priority_options is not None:
            response["priority_options"] = priority_options
            
        if usd_price is not None:
            response["usd_price"] = usd_price
            
        return response 