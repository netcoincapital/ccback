import os
import sys

# تنظیم مسیر اصلی پروژه به PYTHONPATH
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# اجرای اسکریپت شبیه‌سازی قیمت
from CC.utils.price_simulator import NCCPRICE

if __name__ == "__main__":
    NCCPRICE.main()

