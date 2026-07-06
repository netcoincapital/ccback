from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
import logging
from decimal import Decimal
from datetime import datetime
import uuid
import traceback

from database_shop_chat import SessionLocalShopChat, Product
from security.validators import SecurityUtils, InputValidator, ValidationError
from utils.logging_config import get_logger

logger = get_logger(__file__)

shop_api = Blueprint('shop_api', __name__)

@shop_api.route('/shop/products', methods=['GET'])
@SecurityUtils.rate_limit(requests=30, window=60)
def get_products():
    try:
        session = SessionLocalShopChat()
        try:
            category = request.args.get('category')
            is_active = request.args.get('is_active', 'true').lower() == 'true'
            
            query = session.query(Product)
            if category:
                query = query.filter(Product.Category == category)
            if is_active:
                query = query.filter(Product.IsActive == True)
            
            products = query.all()
            
            result = []
            for product in products:
                result.append({
                    'ProductID': product.ProductID,
                    'Name': product.Name,
                    'Description': product.Description,
                    'Price': float(product.Price),
                    'Stock': product.Stock,
                    'ImageURL': product.ImageURL,
                    'Category': product.Category,
                    'IsActive': product.IsActive
                })
            
            return jsonify({
                'success': True,
                'products': result,
                'count': len(result)
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting products: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@shop_api.route('/shop/products', methods=['POST'])
@SecurityUtils.rate_limit(requests=10, window=60)
def create_product():
    try:
        if not request.is_json:
            raise ValidationError("Content-Type must be application/json", 415)
        
        data = request.get_json()
        
        session = SessionLocalShopChat()
        try:
            product = Product(
                ProductID=str(uuid.uuid4()),
                Name=data.get('Name'),
                Description=data.get('Description'),
                Price=Decimal(str(data.get('Price'))),
                Stock=data.get('Stock', 0),
                ImageURL=data.get('ImageURL'),
                Category=data.get('Category'),
                IsActive=data.get('IsActive', True)
            )
            
            session.add(product)
            session.commit()
            
            return jsonify({
                'success': True,
                'product': {
                    'ProductID': product.ProductID,
                    'Name': product.Name,
                    'Price': float(product.Price),
                    'Stock': product.Stock
                }
            }), 201
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error creating product: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@shop_api.route('/shop/products/<product_id>', methods=['GET'])
@SecurityUtils.rate_limit(requests=30, window=60)
def get_product(product_id):
    try:
        session = SessionLocalShopChat()
        try:
            product = session.query(Product).filter(Product.ProductID == product_id).first()
            
            if not product:
                return jsonify({
                    'success': False,
                    'error': 'Product not found'
                }), 404
            
            return jsonify({
                'success': True,
                'product': {
                    'ProductID': product.ProductID,
                    'Name': product.Name,
                    'Description': product.Description,
                    'Price': float(product.Price),
                    'Stock': product.Stock,
                    'ImageURL': product.ImageURL,
                    'Category': product.Category,
                    'IsActive': product.IsActive
                }
            }), 200
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Error getting product: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
