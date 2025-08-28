# دستورات تست سریع Rate Limit

## تنظیمات اولیه
```bash
# تغییر این متغیرها بر اساس سرور شما
export SERVER_URL="http://localhost:5000"
export USER_ID="550e8400-e29b-41d4-a716-446655440000"
```

## 1. تست تکی API /balance
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d "{\"UserID\": \"$USER_ID\"}" \
  "$SERVER_URL/balance" \
  -w "\nStatus Code: %{http_code}\nTime: %{time_total}s\n"
```

## 2. تست تکی API /update-balance
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d "{\"UserID\": \"$USER_ID\"}" \
  "$SERVER_URL/update-balance" \
  -w "\nStatus Code: %{http_code}\nTime: %{time_total}s\n"
```

## 3. تست سریع Rate Limit برای /balance (10 درخواست)
```bash
for i in {1..10}; do
  echo "=== درخواست #$i ==="
  curl -X POST \
    -H "Content-Type: application/json" \
    -d "{\"UserID\": \"$USER_ID\"}" \
    "$SERVER_URL/balance" \
    -w "\nStatus Code: %{http_code}\n" \
    -s | tail -n 1
  sleep 1
done
```

## 4. تست سریع Rate Limit برای /update-balance (3 درخواست)
```bash
for i in {1..3}; do
  echo "=== درخواست #$i ==="
  curl -X POST \
    -H "Content-Type: application/json" \
    -d "{\"UserID\": \"$USER_ID\"}" \
    "$SERVER_URL/update-balance" \
    -w "\nStatus Code: %{http_code}\n" \
    -s | tail -n 1
  sleep 2
done
```

## 5. بررسی وضعیت Redis
```bash
# بررسی اتصال Redis
redis-cli ping

# مشاهده کلیدهای rate limit
redis-cli keys "*:*balance*"

# مشاهده همه کلیدهای rate limit
redis-cli keys "*:*" | head -10
```

## 6. مانیتورینگ Real-time Redis
```bash
# مانیتور کردن دستورات Redis در real-time
redis-cli monitor | grep -i balance
```

## 7. تست با IP های مختلف (شبیه‌سازی)
```bash
# تست با X-Forwarded-For headers مختلف
for ip in 192.168.1.{1..3}; do
  echo "=== تست از IP: $ip ==="
  curl -X POST \
    -H "Content-Type: application/json" \
    -H "X-Forwarded-For: $ip" \
    -d "{\"UserID\": \"$USER_ID\"}" \
    "$SERVER_URL/balance" \
    -w "\nStatus Code: %{http_code}\n" \
    -s | tail -n 1
done
```

## 8. اجرای اسکریپت‌های کامل

### اسکریپت Bash:
```bash
chmod +x test_balance_rate_limit.sh
./test_balance_rate_limit.sh
```

### اسکریپت Python:
```bash
# نصب dependencies
pip install requests redis

# اجرا با تنظیمات پیش‌فرض
python test_rate_limit_detailed.py

# اجرا با آدرس سرور سفارشی
python test_rate_limit_detailed.py "http://your-server:5000" "your-user-id"
```

## نتایج مورد انتظار:

### ✅ حالت عادی (Status 200):
```json
{
  "UserID": "550e8400-e29b-41d4-a716-446655440000",
  "Balances": [...],
  "success": true
}
```

### ❌ Rate Limited (Status 429):
```json
{
  "error": "Rate limit exceeded"
}
```

### ⚠️ خطای سرور (Status 500):
```json
{
  "error_type": "internal_error",
  "message": "...",
  "success": false
}
```

## نکات مهم:

1. **Rate Limit محلی است**: از سمت سرور خودتان اعمال می‌شود
2. **بر اساس IP**: هر IP محدودیت جداگانه دارد
3. **Redis وابسته**: اگر Redis خاموش باشد، rate limit غیرفعال است
4. **محدودیت‌ها**:
   - `/balance`: 10 درخواست در دقیقه
   - `/update-balance`: 2 درخواست در 5 دقیقه


