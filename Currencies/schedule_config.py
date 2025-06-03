from utils.logging_config import get_logger

# Configure logging
logger = get_logger(__file__)
logger.info("Loading schedule configuration")

SCHEDULE_CONFIG = [
    {"interval": 5 * 60, "packages": [0]},            # پکیج 1
    {"interval": 10 * 60, "packages": [1]},           # پکیج 2
    {"interval": 15 * 60, "packages": [2]},           # پکیج 3
    {"interval": 60 * 60, "packages": list(range(3, 9))},     # پکیج 4 تا 9
    {"interval": 180 * 60, "packages": list(range(9, 18))}    # پکیج 10 تا 18
]

BATCH_SIZE = 50  # تعداد ارزها در هر پکیج

logger.info(f"Schedule configuration loaded: {len(SCHEDULE_CONFIG)} schedules defined")
logger.info(f"Batch size set to: {BATCH_SIZE} coins per package")

# Log detailed schedule
for i, config in enumerate(SCHEDULE_CONFIG):
    interval_minutes = config["interval"] // 60
    packages_count = len(config["packages"])
    logger.debug(f"Schedule {i+1}: Every {interval_minutes} minutes for {packages_count} package(s): {config['packages']}")