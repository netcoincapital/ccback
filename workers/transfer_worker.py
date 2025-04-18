import sys
import os
import logging

# Add the parent directory to the sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.TransferHandler import run_transfer_worker
from utils.logging_config import setup_logging

if __name__ == "__main__":
    # Configure logging
    setup_logging()
    logging.info("Starting transfer worker")
    
    try:
        # Run the transfer worker
        run_transfer_worker()
    except KeyboardInterrupt:
        logging.info("Transfer worker stopped by user")
    except Exception as e:
        logging.error(f"Transfer worker encountered an error: {str(e)}") 