# راهنمای رفع خطاهای CoinCeeper

این راهنما به شما کمک می‌کند تا مشکلات رایج در اپلیکیشن CoinCeeper را عیب‌یابی و رفع کنید.

## خطای "Internal server error"

اگر در تمام API‌ها خطای "Internal server error" دریافت می‌کنید، علت احتمالی یکی از موارد زیر است:

### 1. مشکل در اتصال به پایگاه داده

#### تشخیص:
1. با مرورگر به آدرس `http://localhost:5000/api/database-test` بروید
2. پیام خطای دقیق را بررسی کنید

#### راه حل:
- اطمینان حاصل کنید که سرور MySQL در حال اجراست
- فایل `.env` را باز کنید و متغیر `DATABASE_URL` را بررسی کنید:
  ```
  DATABASE_URL=mysql+mysqlconnector://coincee:password@localhost/coincee
  ```
- اطمینان حاصل کنید که:
  - نام کاربری (`coincee`) و رمز عبور (`password`) صحیح است
  - دیتابیس `coincee` در MySQL وجود دارد
  - درایور `mysql-connector-python` نصب شده است: `pip install mysql-connector-python`

- یا برای آزمایش از SQLite استفاده کنید:
  در فایل `.env` خط مربوط به MySQL را با # کامنت کنید و خط SQLite را فعال کنید:
  ```
  # DATABASE_URL=mysql+mysqlconnector://coincee:password@localhost/coincee
  DATABASE_URL=sqlite:///instance/app.db
  ```

### 2. مشکل در کلید رمزنگاری AES

#### تشخیص:
1. با مرورگر به آدرس `http://localhost:5000/api/config-test` بروید
2. بررسی کنید که آیا `AES_SECRET_KEY` تنظیم شده است

#### راه حل:
- در فایل `.env` اطمینان حاصل کنید که `AES_SECRET_KEY` مقداری با طول دقیقا 16، 24 یا 32 بایت دارد:
  ```
  AES_SECRET_KEY=CoinCeeperSecretKey123456
  ```

### 3. مشکل در بسته‌های پایتون

#### تشخیص:
1. اسکریپت `setup_env.py` را اجرا کنید: `python setup_env.py`
2. بسته‌های گمشده را بررسی کنید

#### راه حل:
- تمام بسته‌های مورد نیاز را نصب کنید:
  ```
  pip install -r requirements.txt
  ```
- به طور خاص، اطمینان حاصل کنید که بسته‌های زیر نصب شده‌اند:
  ```
  pip install flask sqlalchemy pika flask_cors flask_wtf flask_openapi3 pydantic bip_utils pycryptodome python-dotenv mysql-connector-python
  ```

### 4. مشکل در متغیرهای محیطی

#### تشخیص:
1. با مرورگر به آدرس `http://localhost:5000/api/config-test` بروید
2. متغیرهای محیطی گمشده را بررسی کنید

#### راه حل:
- اطمینان حاصل کنید که فایل `.env` در مسیر اصلی پروژه وجود دارد
- متغیرهای محیطی ضروری را در آن قرار دهید:
  ```
  DATABASE_URL=mysql+mysqlconnector://coincee:password@localhost/coincee
  AES_SECRET_KEY=CoinCeeperSecretKey123456
  FLASK_ENV=development
  SECRET_KEY=CoinCeeperAppSecretKey123
  ```

### 5. فعال کردن حالت دیباگ برای دیدن خطای دقیق

برای دیدن خطای دقیق، حالت دیباگ را فعال کنید:

1. در فایل `.env` اطمینان حاصل کنید که:
   ```
   FLASK_ENV=development
   ```

2. برنامه را دوباره اجرا کنید:
   ```
   python app.py
   ```

3. حالا وقتی درخواست API می‌دهید، جزئیات کامل خطا را خواهید دید.

## مشاهده لاگ‌ها

برای بررسی دقیق‌تر خطاها، فایل‌های لاگ زیر را بررسی کنید:

1. پوشه `Logs/{تاریخ امروز}/` - لاگ‌های هر ماژول به صورت جداگانه
2. پوشه `Log/` - لاگ‌های خطاهای عمومی

همچنین می‌توانید با خط فرمان به راحتی لاگ‌ها را مشاهده کنید:
```
tail -f Logs/$(date +%Y-%m-%d)/*.log
```

## تست دستی اتصال به پایگاه داده

برای تست دستی اتصال به پایگاه داده MySQL:

```python
import mysql.connector

try:
    conn = mysql.connector.connect(
        user='coincee', 
        password='password',
        host='localhost',
        database='coincee'
    )
    print("Connected:", conn.is_connected())
    conn.close()
except Exception as e:
    print("Error:", e)
```

## راه‌اندازی محیط از ابتدا

برای راه‌اندازی کامل محیط، این مراحل را دنبال کنید:

1. اطمینان حاصل کنید که MySQL نصب و در حال اجراست
2. دیتابیس جدید با نام `coincee` ایجاد کنید:
   ```sql
   CREATE DATABASE coincee;
   CREATE USER 'coincee'@'localhost' IDENTIFIED BY 'password';
   GRANT ALL PRIVILEGES ON coincee.* TO 'coincee'@'localhost';
   FLUSH PRIVILEGES;
   ```
3. محیط مجازی پایتون ایجاد کنید و فعال کنید:
   ```
   python -m venv venv
   # در Windows:
   venv\Scripts\activate
   # در Linux/Mac:
   source venv/bin/activate
   ```
4. بسته‌های مورد نیاز را نصب کنید:
   ```
   pip install -r requirements.txt
   ```
5. فایل `.env` را بر اساس نمونه ارائه شده ایجاد کنید
6. اسکریپت بررسی محیط را اجرا کنید:
   ```
   python setup_env.py
   ```
7. برنامه را اجرا کنید:
   ```
   python app.py
   ```

## نمونه درخواست‌های API برای تست

برای تست API ها بعد از رفع مشکل، می‌توانید از نمونه درخواست‌های زیر استفاده کنید:

### تست سلامت برنامه
```
GET http://localhost:5000/
```

### تست اتصال به پایگاه داده
```
GET http://localhost:5000/api/database-test
```

### تست تنظیمات محیطی
```
GET http://localhost:5000/api/config-test
```

### تولید کیف پول جدید
```
POST http://localhost:5000/api/generate-wallet
Content-Type: application/json

{
  "WalletName": "My Test Wallet"
}
``` 