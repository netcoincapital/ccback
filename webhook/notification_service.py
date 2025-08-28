import logging
import json
import requests
import os
from CC.utils.logging_config import get_logger
from sqlalchemy.orm import Session
from CC.database import SessionLocal, UserDevices
from CC.config.firebase import send_notification

# Configure logger
logger = get_logger(__file__)

class NotificationService:
    """
    Notification service class for sending information to frontend and push notifications
    """
    
    def __init__(self):
        """
        Initialize notification service
        """
        # Notification service configuration can be added here
        pass
    
    def notify(self, transaction_type, transaction_id, relevant_addresses, webhook_data):
        """
        Send notification to frontend and users about new transaction
        
        Args:
            transaction_type (str): Type of transaction ('contract_event' or 'address_transaction')
            transaction_id (str): Transaction ID
            relevant_addresses (list): List of related address information
            webhook_data (dict): Complete webhook data
            
        Returns:
            bool: Operation result
        """
        try:
            logger.warning("⚠️ notify method called")
            logger.info(f"Sending notification for transaction {transaction_id}")
            
            # Extract wallet IDs and user IDs (assuming they are available)
            wallet_ids = list(set([address_info['wallet_id'] for address_info in relevant_addresses]))
            
            # Prepare notification data
            notification_data = {
                'type': 'new_transaction',
                'transaction_type': transaction_type,
                'transaction_id': transaction_id,
                'affected_wallets': wallet_ids,
                'timestamp': webhook_data.get('timestamp'),
                'blockchain': webhook_data.get('chain')
            }
            
            logger.debug(f"Notification data: {notification_data}")
            
            # Send notification through WebSocket or API to frontend (only if URL is configured)
            frontend_url = os.environ.get("FRONTEND_NOTIFICATION_URL")
            if frontend_url:
                self._send_to_frontend(notification_data)
            
            # Extract transaction details from webhook_data
            direction = webhook_data.get('direction')
            amount = webhook_data.get('amount')
            symbol = webhook_data.get('token')
            from_address = webhook_data.get('from')
            to_address = webhook_data.get('to')
            wallet_id = wallet_ids[0] if wallet_ids else None
            
            # Debug: Log all extracted values
            logger.info(f"[DEBUG] Extracted values for notification:")
            logger.info(f"  - direction: {direction} (type: {type(direction)})")
            logger.info(f"  - amount: {amount} (type: {type(amount)})")
            logger.info(f"  - symbol: {symbol} (type: {type(symbol)})")
            logger.info(f"  - from_address: {from_address}")
            logger.info(f"  - to_address: {to_address}")
            logger.info(f"  - wallet_id: {wallet_id}")
            
            # Validate required fields for notification
            if not direction or direction not in ['inbound', 'outbound']:
                logger.warning(f"Invalid or missing direction: {direction}. Skipping notification.")
                return False
                
            if not amount or not symbol:
                logger.warning(f"Missing amount or symbol. Amount: {amount}, Symbol: {symbol}. Skipping notification.")
                return False
            
            # Send push notifications to users' devices
            self._send_push_notifications(
                wallet_ids, 
                transaction_id, 
                transaction_type,
                direction=direction,
                amount=amount,
                symbol=symbol,
                from_address=from_address,
                to_address=to_address,
                wallet_id=wallet_id
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending notifications: {str(e)}", exc_info=True)
            return False
    
    def _send_to_frontend(self, data):
        """
        Send data to frontend through REST API
        
        Args:
            data (dict): Data to be sent
            
        Returns:
            bool: Operation result
        """
        try:
            frontend_url = os.environ.get("FRONTEND_NOTIFICATION_URL")
            if not frontend_url:
                logger.warning("Frontend notification URL not configured. Skipping frontend notification.")
                return False
                
            logger.info("Sending notification to frontend")
            logger.debug(f"Sent data: {data}")
            
            # Send data to frontend API
            response = requests.post(
                frontend_url,
                json=data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                logger.info("Notification successfully sent to frontend")
                logger.debug(f"API response: {response.text}")
                return True
            else:
                logger.error(f"Error sending notification to frontend. Status code: {response.status_code}")
                logger.debug(f"API response: {response.text}")
                return False
            
        except Exception as e:
            logger.error(f"Error sending to frontend: {str(e)}", exc_info=True)
            return False
    
    def _send_push_notifications(self, wallet_ids, transaction_id, transaction_type, direction=None, amount=None, symbol=None, from_address=None, to_address=None, wallet_id=None):
        """
        Send push notifications to users' devices
        
        Args:
            wallet_ids (list): List of wallet IDs
            transaction_id (str): Transaction ID
            transaction_type (str): Transaction type
            direction (str, optional): Transaction direction ('inbound' or 'outbound')
            amount (str, optional): Transaction amount
            symbol (str, optional): Token symbol
            from_address (str, optional): Sender address
            to_address (str, optional): Recipient address
            wallet_id (str, optional): Wallet ID
            
        Returns:
            bool: Operation result
        """
        try:
            if not wallet_ids:
                logger.warning("No wallet IDs found for sending push notification")
                return False
            
            logger.info(f"Sending push notifications for {len(wallet_ids)} wallets")
            
            # Get device tokens for related wallets
            device_tokens = self._get_device_tokens_for_wallets(wallet_ids)
            
            if not device_tokens:
                logger.warning("No device tokens found for sending push notification")
                return False
            
            logger.info(f"Sending push notifications to {len(device_tokens)} devices")
            
            # Prepare notification message
            notification_message = self._create_notification_message(
                transaction_id, 
                transaction_type,
                direction=direction,
                amount=amount,
                symbol=symbol,
                from_address=from_address,
                to_address=to_address,
                wallet_id=wallet_id
            )
            
            if not notification_message:
                logger.warning("No notification message generated, skipping push")
                return False
            
            # Send notifications to each device
            success_count = 0
            for token in device_tokens:
                if self._send_push_to_device(token, notification_message):
                    success_count += 1
            
            logger.info(f"Push notification successfully sent to {success_count} out of {len(device_tokens)} devices")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Error sending push notifications: {str(e)}", exc_info=True)
            return False
    
    def _get_device_tokens_for_wallets(self, wallet_ids):
        """
        Get device tokens for wallets from database
        
        Args:
            wallet_ids (list): List of wallet IDs
            
        Returns:
            list: List of device tokens
        """
        logger.debug(f"Getting device tokens for wallets {wallet_ids}")
        
        # Get device tokens from database
        session = SessionLocal()
        try:
            # Get all device tokens for given wallets
            devices = session.query(UserDevices).filter(
                UserDevices.WalletID.in_(wallet_ids)
            ).all()
            
            # Extract device tokens
            tokens = [device.DeviceToken for device in devices]
            
            logger.debug(f"Found {len(tokens)} device tokens")
            return tokens
            
        except Exception as e:
            logger.error(f"Error retrieving device tokens: {str(e)}", exc_info=True)
            return []
        finally:
            session.close()
    
    def _create_notification_message(self, transaction_id, transaction_type, direction=None, amount=None, symbol=None, from_address=None, to_address=None, wallet_id=None):
        """
        Create notification message based on transaction type and direction
        
        Args:
            transaction_id (str): Transaction ID
            transaction_type (str): Transaction type
            direction (str, optional): Transaction direction ('inbound' or 'outbound')
            amount (str, optional): Transaction amount
            symbol (str, optional): Token symbol
            from_address (str, optional): Sender address
            to_address (str, optional): Recipient address
            wallet_id (str, optional): Wallet ID
            
        Returns:
            dict: Notification message or None if no valid notification should be sent
        """
        def shorten_address(address):
            """Shorten address to first 6 and last 4 characters"""
            if not address or len(address) < 10:
                return address
            return f"{address[:6]}...{address[-4:]}"

        # Validate required fields
        if not direction or direction not in ['inbound', 'outbound']:
            logger.warning(f"Invalid or missing direction: {direction}. Skipping notification.")
            return None
            
        if not amount or not symbol:
            logger.warning(f"Missing amount or symbol. Amount: {amount}, Symbol: {symbol}. Skipping notification.")
            return None

        # Map direction to frontend-expected type
        notification_type = "receive" if direction == 'inbound' else "send"

        # Set message based on transaction direction
        if direction == 'outbound':
            title = f"💸 Sent: {amount} {symbol}"
            body = f"To {shorten_address(to_address)}"
        else:  # inbound
            title = f"💰 Received: {amount} {symbol}"
            body = f"From {shorten_address(from_address)}"
        
        return {
            "title": title,
            "body": body,
            "data": {
                "transaction_id": transaction_id,
                "type": notification_type,  # Changed from transaction_type to send/receive
                "direction": direction,
                "amount": amount,
                "currency": symbol,  # Changed from symbol to currency for frontend compatibility
                "symbol": symbol,    # Keep both for backward compatibility
                "from_address": from_address,
                "to_address": to_address,
                "wallet_id": wallet_id
            }
        }
    
    def _send_push_to_device(self, device_token, message):
        """
        Send push notification to a specific device using FCM
        
        Args:
            device_token (str): Device token
            message (dict): Notification message
            
        Returns:
            bool: Operation result
        """
        try:
            if not message:
                logger.warning("No message provided for push notification")
                return False
                
            logger.debug(f"Sending push notification to device {device_token}")
            
            # Call notification sending function from firebase module
            title = message["title"]
            body = message["body"]
            data = message["data"]
            
            # Send notification using Firebase
            return send_notification(device_token, title, body, data)
            
        except Exception as e:
            logger.error(f"Error sending push notification to device {device_token}: {str(e)}")
            return False 