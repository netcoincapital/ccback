from flask_swagger_ui import get_swaggerui_blueprint
from flask import jsonify
import os

# Swagger configuration
SWAGGER_URL = '/api/docs'  # URL for exposing Swagger UI
API_URL = '/api/swagger.json'  # URL to access API docs

# Swagger metadata
swagger_config = {
    "swagger": "2.0",
    "info": {
        "title": "IronWallet API",
        "description": "API for IronWallet cryptocurrency wallet management",
        "version": "1.0.0",
        "contact": {
            "email": "support@ironwallet.com"
        },
        "license": {
            "name": "Proprietary",
            "url": "https://ironwallet.com/license"
        }
    },
    "basePath": "/",
    "schemes": [
        "https",
        "http"
    ],
    "securityDefinitions": {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-KEY"
        }
    },
    "tags": [
        {
            "name": "Wallet Management",
            "description": "Wallet creation, import, and management operations"
        },
        {
            "name": "Transactions",
            "description": "Transaction operations"
        },
        {
            "name": "Currencies",
            "description": "Currency operations"
        }
    ],
    "paths": {},
    "definitions": {}
}

# Create Swagger UI blueprint
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={
        'app_name': "IronWallet API"
    }
)

def get_swagger_json():
    """
    Generate Swagger JSON specification
    
    This function is called by the route handler to generate the Swagger JSON
    specification dynamically based on the registered routes and schemas.
    
    Returns:
        dict: Swagger JSON specification
    """
    # Import schemas to include in Swagger spec
    from schemas import (
        WalletGenerationRequest,
        WalletGenerationResponse,
        WalletGenerationStatusResponse,
        WalletGenerationSyncResponse,
        WalletImportRequest,
        WalletImportResponse,
        MnemonicValidationRequest,
        MnemonicValidationResponse,
        ErrorResponse
    )
    
    # Add schema definitions
    swagger_config["definitions"] = {
        "WalletGenerationRequest": WalletGenerationRequest.schema(),
        "WalletGenerationResponse": WalletGenerationResponse.schema(),
        "WalletGenerationStatusResponse": WalletGenerationStatusResponse.schema(),
        "WalletGenerationSyncResponse": WalletGenerationSyncResponse.schema(),
        "WalletImportRequest": WalletImportRequest.schema(),
        "WalletImportResponse": WalletImportResponse.schema(),
        "MnemonicValidationRequest": MnemonicValidationRequest.schema(),
        "MnemonicValidationResponse": MnemonicValidationResponse.schema(),
        "ErrorResponse": ErrorResponse.schema()
    }
    
    return swagger_config

def register_swagger(app):
    """
    Register Swagger UI blueprint and routes with Flask app
    
    Args:
        app: Flask application instance
    """
    # Register Swagger UI blueprint
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)
    
    # Add route for Swagger JSON
    @app.route(API_URL)
    def swagger_json():
        return jsonify(get_swagger_json()) 