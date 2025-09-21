# 📊 توضیح جدول انتخاب API برای چارت‌ها

## 🔍 **معنای علامت‌ها:**

### ✅ **آپدیت زنده (سبز):**
- چارت **به صورت زنده** آپدیت می‌شود
- از API `/chart-live-update` استفاده می‌کند
- مناسب برای **trading** و **مانیتورینگ real-time**

### ❌ **بدون آپدیت زنده (قرمز):**
- چارت **استاتیک** است (داده‌های تاریخی ثابت)
- نیازی به آپدیت زنده **ندارد** (چون داده‌ها تاریخی هستند)
- مناسب برای **تحلیل** و **بررسی روندهای گذشته**

---

## 📋 **توضیح دقیق هر بازه:**

### 1. **⏰ بازه‌های کوتاه (Real-time)**

#### **1h - چارت ساعتی:**
- **✅ آپدیت زنده:** بله، هر 30 ثانیه
- **دلیل:** معامله‌گران نیاز به اطلاعات لحظه‌ای دارند
- **کاربرد:** Day Trading, Scalping

#### **1d - چارت روزانه:**
- **✅ آپدیت زنده:** بله، هر 1 دقیقه
- **دلیل:** نمایش روند روز جاری
- **کاربرد:** Swing Trading, تحلیل روزانه

#### **1w - چارت هفتگی:**
- **✅ آپدیت زنده:** بله، هر 5 دقیقه
- **دلیل:** نمایش روند هفته جاری
- **کاربرد:** تحلیل کوتاه مدت، برنامه‌ریزی هفتگی

---

### 2. **📊 بازه‌های تاریخی (Static)**

#### **1m - چارت ماهانه:**
- **❌ آپدیت زنده:** خیر
- **دلیل:** داده‌های **تاریخی ثابت** ماه گذشته
- **کاربرد:** تحلیل عملکرد ماهانه، مقایسه ماه‌ها
- **منطق:** ماه گذشته تغییر نمی‌کند!

#### **3m - چارت سه‌ماهه:**
- **❌ آپدیت زنده:** خیر  
- **دلیل:** داده‌های **تاریخی ثابت** 3 ماه گذشته
- **کاربرد:** تحلیل روند میان مدت، فصلی
- **منطق:** 3 ماه گذشته تغییر نمی‌کند!

#### **1y - چارت سالانه:**
- **❌ آپدیت زنده:** خیر
- **دلیل:** داده‌های **تاریخی ثابت** سال گذشته  
- **کاربرد:** تحلیل بلندمدت، روندهای سالانه
- **منطق:** سال گذشته تغییر نمی‌کند!

---

## 🤔 **چرا بازه‌های طولانی آپدیت زنده ندارند؟**

### **منطق:**
1. **داده‌های تاریخی ثابت هستند** - ماه گذشته تغییر نمی‌کند
2. **صرفه‌جویی در منابع** - نیازی به آپدیت مداوم نیست
3. **بهینه‌سازی عملکرد** - کمتر API call = سرعت بیشتر

### **مثال:**
- چارت ماه آگوست 2024 **همیشه یکسان** خواهد بود
- چارت سال 2023 **هرگز تغییر نخواهد کرد**
- ولی چارت امروز **هر لحظه تغییر می‌کند**

---

## 🔄 **استراتژی ترکیبی برای چارت کامل:**

### **چارت پیشرفته با تمام بازه‌ها:**

```javascript
class AdvancedChart {
  constructor(symbol, fiat = 'USD') {
    this.symbol = symbol;
    this.fiat = fiat;
    this.currentTimeframe = '1d';
    this.liveUpdateInterval = null;
  }
  
  async switchTimeframe(timeframe) {
    this.currentTimeframe = timeframe;
    
    // متوقف کردن آپدیت زنده قبلی
    if (this.liveUpdateInterval) {
      clearInterval(this.liveUpdateInterval);
      this.liveUpdateInterval = null;
    }
    
    // دریافت داده‌های جدید
    const data = await this.getDataForTimeframe(timeframe);
    this.renderChart(data);
    
    // راه‌اندازی آپدیت زنده (فقط برای بازه‌های کوتاه)
    if (['1h', '1d', '1w'].includes(timeframe)) {
      this.startLiveUpdates(timeframe);
    }
  }
  
  async getDataForTimeframe(timeframe) {
    const apiConfig = {
      '1h': { api: 'chart-data', points: 60, live: true },
      '1d': { api: 'chart-data', points: 24, live: true },
      '1w': { api: 'chart-data', points: 168, live: true },
      '1m': { api: 'historical-prices', points: 30, live: false },
      '3m': { api: 'historical-prices', points: 90, live: false },
      '1y': { api: 'historical-prices', points: 365, live: false }
    };
    
    const config = apiConfig[timeframe];
    
    if (config.api === 'chart-data') {
      return this.fetchChartData(timeframe, config.points);
    } else {
      return this.fetchHistoricalData(timeframe);
    }
  }
  
  startLiveUpdates(timeframe) {
    const intervals = {
      '1h': 30000,  // 30 ثانیه
      '1d': 60000,  // 1 دقیقه  
      '1w': 300000  // 5 دقیقه
    };
    
    this.liveUpdateInterval = setInterval(async () => {
      const liveData = await this.fetchLiveUpdate();
      this.updateChartLastPoint(liveData);
    }, intervals[timeframe]);
  }
  
  async fetchLiveUpdate() {
    const response = await fetch('/api/chart-live-update', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        Symbol: [this.symbol],
        FiatCurrency: this.fiat
      })
    });
    
    const data = await response.json();
    return data.data.live_prices[this.symbol];
  }
}

// استفاده
const chart = new AdvancedChart('BTC', 'USD');

// تغییر به چارت روزانه (با آپدیت زنده)
chart.switchTimeframe('1d');

// تغییر به چارت ماهانه (بدون آپدیت زنده)  
chart.switchTimeframe('1m');
```

---

## 💡 **نکات مهم:**

### **1. بازه‌های Real-time (✅):**
- **مزیت:** اطلاعات لحظه‌ای
- **کاربرد:** معاملات، مانیتورینگ
- **هزینه:** API calls بیشتر

### **2. بازه‌های Historical (❌):**
- **مزیت:** داده‌های کامل و دقیق
- **کاربرد:** تحلیل، گزارش‌گیری
- **هزینه:** API calls کمتر

### **3. ترکیب هوشمند:**
```javascript
// برای چارت‌های تعاملی
if (timeframe === 'current') {
  // نمایش چارت روزانه + آپدیت زنده
  showChart('1d', true);
} else {
  // نمایش چارت تاریخی بدون آپدیت
  showChart(timeframe, false);
}
```

## 🎯 **خلاصه:**
- **❌ (قرمز) = بدون آپدیت زنده** (چون نیازی نیست)
- **✅ (سبز) = با آپدیت زنده** (چون داده‌ها تغییر می‌کنند)

**همه API ها کاملاً کار می‌کنند، فقط استراتژی استفاده متفاوت است! 🚀**
