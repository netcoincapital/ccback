#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы webhook
"""

import requests
import json
import sys
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_webhook_route(host='http://localhost:5000'):
    """
    Проверка доступности тестового webhook маршрута
    """
    url = f"{host}/webhook/test"
    
    logger.info(f"Testing webhook route: {url}")
    
    try:
        response = requests.get(url, timeout=5)
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            logger.info(f"Response body: {response.json()}")
            return True
        else:
            logger.error(f"Error response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error testing webhook route: {str(e)}")
        return False

def send_test_transaction_webhook(host='http://localhost:5000'):
    """
    Отправка тестового webhook для симуляции транзакции
    """
    url = f"{host}/webhook/tatum/transaction"
    
    logger.info(f"Sending test transaction webhook to: {url}")
    
    # Создание тестовых данных транзакции
    test_data = {
        "type": "ADDRESS_TRANSACTION",
        "chain": "ETH",
        "transactionId": "0x123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "blockHeight": 12345678,
        "from": "0x1234567890123456789012345678901234567890",
        "to": "0x0987654321098765432109876543210987654321",
        "value": "1000000000000000000",  # 1 ETH
        "timestamp": "2025-04-07T06:33:19.992Z"
    }
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, json=test_data, headers=headers, timeout=10)
        logger.info(f"Response status code: {response.status_code}")
        
        if response.status_code in [200, 202]:
            logger.info(f"Response body: {response.json()}")
            return True
        else:
            logger.error(f"Error response: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending test webhook: {str(e)}")
        return False

if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:5000'
    
    logger.info(f"Testing webhooks on host: {host}")
    
    # Сначала проверяем тестовый маршрут
    if test_webhook_route(host):
        logger.info("✅ Webhook test route is working!")
        
        # Теперь отправляем тестовую транзакцию
        if send_test_transaction_webhook(host):
            logger.info("✅ Transaction webhook processed successfully!")
        else:
            logger.error("❌ Transaction webhook failed!")
    else:
        logger.error("❌ Webhook test route is not working!")
        
    logger.info("Webhook testing completed") 