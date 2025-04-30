"""
Fee Estimator API

A Flask API for estimating transaction fees across multiple blockchain networks.
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any, Optional
import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from .estimator import estimate_fee, get_supported_chains, get_chain_info
from CC.utils.logging_config import get_logger

# Get logger for this module
logger = get_logger(__file__)

# Create a Blueprint instead of a Flask app
fee_estimator_bp = Blueprint('fee_estimator', __name__)

@fee_estimator_bp.route("/estimate-fee", methods=["POST"])
def api_estimate_fee():
    """
    Estimate transaction fee for the given blockchain and parameters.
    
    Expected JSON body:
    {
        "blockchain": "ethereum",
        "from_address": "0x...",
        "to_address": "0x...",
        "amount": 0.1,
        "token_contract": "0x..." (optional)
    }
    """
    try:
        data = request.get_json()
        logger.info(f"Received fee estimation request: {data}")
        
        # Validate required fields
        required_fields = ["blockchain", "from_address", "to_address", "amount"]
        for field in required_fields:
            if field not in data:
                logger.warning(f"Missing required field: {field}")
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Extract parameters
        blockchain = data["blockchain"]
        from_address = data["from_address"]
        to_address = data["to_address"]
        amount = float(data["amount"])
        token_contract = data.get("token_contract")
        
        logger.debug(f"Processing fee estimation for blockchain: {blockchain}")
        
        # Estimate fee
        result = estimate_fee(
            blockchain=blockchain,
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            token_contract=token_contract
        )
        
        logger.info(f"Fee estimation completed successfully for {blockchain}")
        return jsonify(result)
    
    except ValueError as e:
        logger.error(f"Value error in fee estimation: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Unexpected error in fee estimation: {str(e)}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred"}), 500

@fee_estimator_bp.route("/supported-chains", methods=["GET"])
def api_supported_chains():
    """Get list of supported blockchains."""
    logger.info("Fetching supported chains")
    chains = get_supported_chains()
    return jsonify({"chains": chains})

@fee_estimator_bp.route("/chain-info/<blockchain>", methods=["GET"])
def api_chain_info(blockchain):
    """Get information about a specific blockchain."""
    try:
        logger.info(f"Fetching chain info for {blockchain}")
        info = get_chain_info(blockchain)
        return jsonify(info)
    except ValueError as e:
        logger.warning(f"Chain info not found for {blockchain}: {str(e)}")
        return jsonify({"error": str(e)}), 404

@fee_estimator_bp.route("/health", methods=["GET"])
def health_check():
    """API health check endpoint."""
    logger.debug("Health check requested")
    return jsonify({"status": "healthy"}) 