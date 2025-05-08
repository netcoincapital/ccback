import os
import json
import logging
import firebase_admin
from firebase_admin import credentials, messaging
from utils.logging_config import get_logger
import pathlib

# Configure logger
logger = get_logger(__file__)

# Is Firebase initialized?
firebase_initialized = False

# Try to import tenacity, if not available use a simple retry decorator
try:
    from tenacity import retry, stop_after_attempt, wait_exponential
    TENACITY_AVAILABLE = True
except ImportError:
    TENACITY_AVAILABLE = False
    logger.warning("tenacity package not available. Using simple retry mechanism.")
    
    def retry(*args, **kwargs):
        def decorator(func):
            def wrapper(*args, **kwargs):
                max_attempts = 3
                for attempt in range(max_attempts):
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        if attempt == max_attempts - 1:
                            raise
                        logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                        import time
                        time.sleep(2 ** attempt)  # Simple exponential backoff
                return None
            return wrapper
        return decorator

def initialize_firebase():
    """
    Initialize Firebase using service account key file
    
    This function sets up Firebase using the service account key file.
    First, it checks for the private key file in the config folder, then checks environment variables.
    """
    global firebase_initialized
    
    if firebase_initialized:
        logger.debug("Firebase already initialized")
        return True
    
    try:
        # Path to Firebase private key file in config folder
        base_dir = pathlib.Path(__file__).parent  # config directory
        service_account_path = base_dir / 'coinceeper-f2eaf-firebase-adminsdk-fbsvc-4f2bc9645c.json'
        
        if service_account_path.exists():
            logger.info(f"Using Firebase credentials from file: {service_account_path}")
            cred = credentials.Certificate(str(service_account_path))
        else:
            # If key file doesn't exist in config folder, check environment variables
            firebase_credentials_json = os.environ.get('FIREBASE_CREDENTIALS')
            firebase_credentials_path = os.environ.get('FIREBASE_CREDENTIALS_PATH')
            
            if firebase_credentials_json:
                logger.info("Initializing Firebase using credentials from environment variable")
                try:
                    # Convert JSON credentials from environment variable
                    cred_dict = json.loads(firebase_credentials_json)
                    cred = credentials.Certificate(cred_dict)
                except json.JSONDecodeError:
                    logger.error("Invalid JSON in FIREBASE_CREDENTIALS environment variable")
                    return False
            elif firebase_credentials_path:
                logger.info(f"Initializing Firebase using credentials from file: {firebase_credentials_path}")
                # Read credentials from file
                cred = credentials.Certificate(firebase_credentials_path)
            else:
                logger.warning("No Firebase credentials found. Firebase notifications disabled.")
                return False
        
        # Initialize Firebase app
        firebase_admin.initialize_app(cred)
        firebase_initialized = True
        logger.info("Firebase initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing Firebase: {str(e)}", exc_info=True)
        return False

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10)) if TENACITY_AVAILABLE else retry()
def send_notification(token, title, body, data=None, priority='normal'):
    """
    Send Firebase notification to a device with retry capability in case of failure
    
    Args:
        token (str): FCM device token
        title (str): Notification title
        body (str): Notification body
        data (dict, optional): Additional data to send
        priority (str, optional): Notification priority ('normal' or 'high')
        
    Returns:
        bool: Success or failure
    """
    if not firebase_initialized and not initialize_firebase():
        logger.error("Firebase not initialized and initialization failed")
        return False
    
    try:
        logger.info(f"[FCM] Sending to token: {token}")
        logger.debug(f"[FCM] Title: {title}, Body: {body}, Data: {data}")

        # Convert data to dictionary with string values
        string_data = {k: str(v) for k, v in (data or {}).items()}
        
        # Priority settings for Android and iOS
        android_config = messaging.AndroidConfig(
            priority=priority,
            notification=messaging.AndroidNotification(
                sound='default',
                channel_id='default'
            )
        )
        
        apns_config = messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    sound='default',
                    badge=1
                )
            ),
            headers={'apns-priority': '10' if priority == 'high' else '5'}
        )
        
        # Create combined notification message (notification + data)
        message = messaging.Message(
            token=token,
            notification=messaging.Notification(
                title=title,
                body=body
            ),
            data=string_data,
            android=android_config,
            apns=apns_config
        )
        
        # Send message
        response = messaging.send(message)
        logger.info(f"[FCM] Successfully sent notification: {response}")
        return True
        
    except messaging.UnregisteredError:
        logger.warning(f"[FCM] Device token {token} is no longer valid")
        return False
        
    except messaging.SenderIdMismatchError:
        logger.error("[FCM] Sender ID mismatch. Check Firebase configuration.")
        return False
        
    except messaging.ThirdPartyAuthError:
        logger.error("[FCM] Authentication error with Firebase. Check credentials.")
        return False
        
    except Exception as e:
        logger.error(f"[FCM] Error sending notification: {str(e)}", exc_info=True)
        raise  # Re-raise for retry mechanism 