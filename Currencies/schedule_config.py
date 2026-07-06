from utils.logging_config import get_logger

# Configure logging
logger = get_logger(__file__)
logger.info("Loading schedule configuration")

SCHEDULE_CONFIG = [
    {"interval": 2 * 60, "packages": [0]},            # پکیج 1: هر 2 دقیقه (top coins)
    {"interval": 3 * 60, "packages": [1]},            # پکیج 2: هر 3 دقیقه
    {"interval": 5 * 60, "packages": [2, 3]},         # پکیج 3-4: هر 5 دقیقه
    {"interval": 10 * 60, "packages": [4, 5]},        # پکیج 5-6: هر 10 دقیقه
    {"interval": 15 * 60, "packages": [6, 7]},        # پکیج 7-8: هر 15 دقیقه
    {"interval": 30 * 60, "packages": [8, 9]},        # پکیج 9-10: هر 30 دقیقه
    {"interval": 60 * 60, "packages": [10, 11]}       # پکیج 11-12: هر 1 ساعت
]

# تعداد ارزها در هر پکیج - افزایش از 50 به 100 برای کمتر شدن تعداد پکیج‌ها
BATCH_SIZE = 100  

# توضیحات:
# - کاهش تعداد thread از 18 به 7 برای کاهش race condition
# - افزایش BATCH_SIZE برای کاهش تعداد کل پکیج‌ها
# - افزایش interval برای پکیج‌های با اولویت پایین

logger.info(f"Schedule configuration loaded: {len(SCHEDULE_CONFIG)} schedules defined")
logger.info(f"Batch size set to: {BATCH_SIZE} coins per package")

# Log detailed schedule
for i, config in enumerate(SCHEDULE_CONFIG):
    interval_minutes = config["interval"] // 60
    packages_count = len(config["packages"])
    logger.debug(f"Schedule {i+1}: Every {interval_minutes} minutes for {packages_count} package(s): {config['packages']}")