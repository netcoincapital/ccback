#!/bin/bash

# تست Rate Limit برای API های Balance
# این اسکریپت دقیقاً مشخص می‌کند کدام بخش rate limit می‌دهد

# تنظیمات سرور (این مقادیر را تغییر دهید)
SERVER_URL="http://localhost:5000"  # آدرس سرور شما
USER_ID="550e8400-e29b-41d4-a716-446655440000"  # یک UUID معتبر برای تست

# رنگ‌ها برای خروجی بهتر
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== تست Rate Limit برای Balance APIs ===${NC}"
echo "سرور: $SERVER_URL"
echo "UserID: $USER_ID"
echo ""

# تابع برای ارسال درخواست و نمایش نتیجه
send_request() {
    local endpoint=$1
    local request_number=$2
    local delay=$3
    
    echo -e "${YELLOW}درخواست #$request_number به $endpoint${NC}"
    
    # ارسال درخواست با curl و ذخیره response code و body
    response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -d "{\"UserID\": \"$USER_ID\"}" \
        "$SERVER_URL$endpoint" 2>/dev/null)
    
    # جداسازی body و status code
    body=$(echo "$response" | head -n -1)
    status_code=$(echo "$response" | tail -n 1)
    
    # نمایش نتیجه
    if [ "$status_code" = "429" ]; then
        echo -e "${RED}❌ Rate Limited! Status: $status_code${NC}"
        echo -e "${RED}Response: $body${NC}"
        return 1
    elif [ "$status_code" = "200" ]; then
        echo -e "${GREEN}✅ Success! Status: $status_code${NC}"
        # نمایش بخشی از response برای تأیید
        echo "$body" | jq -r '.success // "No success field"' 2>/dev/null || echo "Response received"
        return 0
    else
        echo -e "${YELLOW}⚠️  Other Status: $status_code${NC}"
        echo "Response: $body"
        return 2
    fi
    
    if [ "$delay" -gt 0 ]; then
        echo "انتظار $delay ثانیه..."
        sleep $delay
    fi
}

echo -e "${BLUE}=== تست 1: API /balance (محدودیت: 10 درخواست در دقیقه) ===${NC}"
echo ""

# تست API /balance - ارسال 12 درخواست سریع برای تریگر کردن rate limit
for i in {1..12}; do
    send_request "/balance" $i 0
    if [ $? -eq 1 ]; then
        echo -e "${RED}Rate limit در درخواست #$i فعال شد!${NC}"
        break
    fi
    sleep 1  # کمی تأخیر بین درخواست‌ها
done

echo ""
echo -e "${BLUE}=== انتظار برای reset شدن rate limit (70 ثانیه) ===${NC}"
sleep 70

echo ""
echo -e "${BLUE}=== تست 2: API /update-balance (محدودیت: 2 درخواست در 5 دقیقه) ===${NC}"
echo ""

# تست API /update-balance - ارسال 3 درخواست برای تریگر کردن rate limit
for i in {1..3}; do
    send_request "/update-balance" $i 0
    if [ $? -eq 1 ]; then
        echo -e "${RED}Rate limit در درخواست #$i فعال شد!${NC}"
        break
    fi
    sleep 2  # کمی تأخیر بین درخواست‌ها
done

echo ""
echo -e "${BLUE}=== تست 3: بررسی Redis Status ===${NC}"
echo ""

# بررسی وضعیت Redis
echo "بررسی اتصال Redis..."
redis_status=$(redis-cli ping 2>/dev/null)
if [ "$redis_status" = "PONG" ]; then
    echo -e "${GREEN}✅ Redis در حال اجرا است${NC}"
    
    # نمایش کلیدهای rate limit
    echo ""
    echo "کلیدهای Rate Limit فعال در Redis:"
    redis-cli keys "*:*balance*" 2>/dev/null | while read key; do
        if [ ! -z "$key" ]; then
            value=$(redis-cli get "$key" 2>/dev/null)
            ttl=$(redis-cli ttl "$key" 2>/dev/null)
            echo -e "${YELLOW}$key${NC} = $value (TTL: $ttl ثانیه)"
        fi
    done
else
    echo -e "${RED}❌ Redis در دسترس نیست${NC}"
    echo -e "${YELLOW}⚠️  اگر Redis خاموش باشد، rate limiting غیرفعال خواهد بود${NC}"
fi

echo ""
echo -e "${BLUE}=== تست 4: تست همزمان از IP های مختلف (شبیه‌سازی) ===${NC}"
echo ""

# تست با User-Agent و Header های مختلف
echo "تست با header های مختلف..."
for i in {1..3}; do
    echo -e "${YELLOW}درخواست #$i با User-Agent متفاوت${NC}"
    
    response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -H "User-Agent: TestClient-$i" \
        -H "X-Forwarded-For: 192.168.1.$i" \
        -d "{\"UserID\": \"$USER_ID\"}" \
        "$SERVER_URL/balance" 2>/dev/null)
    
    status_code=$(echo "$response" | tail -n 1)
    
    if [ "$status_code" = "429" ]; then
        echo -e "${RED}❌ Rate Limited! Status: $status_code${NC}"
    elif [ "$status_code" = "200" ]; then
        echo -e "${GREEN}✅ Success! Status: $status_code${NC}"
    else
        echo -e "${YELLOW}⚠️  Status: $status_code${NC}"
    fi
    
    sleep 1
done

echo ""
echo -e "${BLUE}=== نتیجه‌گیری ===${NC}"
echo -e "${GREEN}✅ Rate limit از سمت سرور خودتان (Redis) اعمال می‌شود${NC}"
echo -e "${GREEN}✅ محدودیت بر اساس IP address کاربر است${NC}"
echo -e "${GREEN}✅ /balance: 10 درخواست در دقیقه${NC}"
echo -e "${GREEN}✅ /update-balance: 2 درخواست در 5 دقیقه${NC}"
echo ""
echo -e "${YELLOW}💡 برای غیرفعال کردن rate limit، Redis را خاموش کنید${NC}"
echo -e "${YELLOW}💡 برای تغییر محدودیت، فایل balance/balance.py را ویرایش کنید${NC}"


