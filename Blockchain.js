/**
 * فایل Blockchain.js
 * ------------------
 * یک سرور Node.js که با Sequelize به دیتابیس MySQL متصل می‌شود.
 * در مسیر /blockchain/batch، آرایه‌ای از آدرس‌ها و بلاک‌چین‌ها
 * در قالب {"requests": [...]} دریافت می‌شود. برای هر آدرس، تمام
 * ارز/توکن‌های مربوط به آن بلاک‌چین از جدول Currencies واکشی شده
 * و اگر IsToken = true باشد، بالانس همان توکن (TRC20/ERC20 و ...) را
 * از API بلاک‌چین می‌گیرد و به صورت یک پاسخ JSON تجمیع‌شده برمی‌گرداند.
 */

const express = require('express');
const axios = require('axios');
const { Sequelize, DataTypes } = require('sequelize');

const app = express();
const port = 3000;
app.use(express.json());

// ----------------------------------------------------------------------------
// اتصال به دیتابیس MySQL از طریق Sequelize
// (اطلاعات باید با دیتابیس شما منطبق باشد)
// ----------------------------------------------------------------------------
const sequelize = new Sequelize('IronWallet', 'root', 'Q#-76(12Kji09?', {
  host: 'localhost',
  dialect: 'mysql',
  logging: false
});

// مدل جدول Currencies مطابق پایتون
const Currencies = sequelize.define('Currencies', {
  CurrencyID: {
    type: DataTypes.STRING,
    primaryKey: true
  },
  CurrencyName: {
    type: DataTypes.STRING
  },
  Icon: {
    type: DataTypes.STRING
  },
  Symbol: {
    type: DataTypes.STRING
  },
  BlockchainID: {
    type: DataTypes.INTEGER
  },
  DecimalPlaces: {
    type: DataTypes.INTEGER
  },
  IsToken: {
    type: DataTypes.BOOLEAN
  },
  SmartContractAddress: {
    type: DataTypes.STRING
  }
}, {
  tableName: 'Currencies',
  timestamps: false
});

// ----------------------------------------------------------------------------
// مپ بین شناسه بلاک‌چین و نام/ API ها (در صورت نیاز)
// ----------------------------------------------------------------------------
const BLOCKCHAIN_APIS = {
  "Bitcoin":  "https://api.blockcypher.com/v1/btc/main/addrs/{public_address}/balance",
  "Ethereum": "https://api.etherscan.io/api?module=account&action=balance&address={public_address}&tag=latest&apikey=YOUR_ETHERSCAN_API_KEY",
  "Tron":     "https://api.trongrid.io/v1/accounts/{public_address}",
  "Binance":  "https://api.bscscan.com/api?module=account&action=balance&address={public_address}&tag=latest&apikey=YOUR_BSCSCAN_API_KEY",
  "Polygon":  "https://api.polygonscan.com/api?module=account&action=balance&address={public_address}&tag=latest&apikey=YOUR_POLYGONSCAN_API_KEY",
  "XRP":       "https://data.ripple.com/v2/accounts/{public_address}/balances",
  "Solana":    "https://api.mainnet-beta.solana.com/",
  "Arbitrum":  "https://api.arbiscan.io/api?module=account&action=balance&address={public_address}&tag=latest&apikey=YOUR_ARBITRUMSCAN_API_KEY",
  "Polkadot":  "https://polkadot.api.example/{public_address}",
  "Avalanche": "https://api.avax.network/ext/bc/C/rpc"
};

const TOKEN_APIS = {
  "Ethereum": "https://api.etherscan.io/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={public_address}&tag=latest&apikey=YOUR_ETHERSCAN_API_KEY",
  "Tron":     "https://api.trongrid.io/v1/accounts/{public_address}/transactions/trc20", // نیاز به پیاده‌سازی جزییات
  "Binance":  "https://api.bscscan.com/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={public_address}&tag=latest&apikey=YOUR_BSCSCAN_API_KEY",
  "Polygon":  "https://api.polygonscan.com/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={public_address}&tag=latest&apikey=YOUR_POLYGONSCAN_API_KEY",
  "XRP":       "https://data.ripple.com/v2/accounts/{public_address}/balances?filt={contract_address}",
  "Solana":    "https://api.mainnet-beta.solana.com/",
  "Arbitrum":  "https://api.arbiscan.io/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={public_address}&tag=latest&apikey=YOUR_ARBITRUMSCAN_API_KEY",
  "Polkadot":  "https://polkadot.api.example/{contract_address}/{public_address}",
  "Avalanche": "https://api.avax.network/ext/bc/C/rpc"
};

// تبدیل عدد BlockchainID به نام بلاک‌چین
function getBlockchainName(blockchainId) {
  // جدول نگاشت؛ بسته به دیتابیس شما تغییر کند
  const mapping = {
    1: "Bitcoin",
    2: "Ethereum",
    3: "Tron",
    4: "Binance",
    5: "Polygon",
    6: "XRP",
    7: "Solana",
    8: "Arbitrum",
    9: "Polkadot",
    10:"Avalanche"
  };
  return mapping[blockchainId];
}

// ----------------------------------------------------------------------------
// Endpoint: /blockchain/batch (نسخه Batch واقعی)
// ----------------------------------------------------------------------------
app.post('/blockchain/batch', async (req, res) => {
  /**
   * انتظار داریم ورودی به‌شکل:
   * {
   *   "requests": [
   *     { "public_address": "...", "blockchain_id": ... },
   *     { "public_address": "...", "blockchain_id": ... },
   *     ...
   *   ]
   * }
   */
  const { requests } = req.body;

  if (!requests || !Array.isArray(requests)) {
    return res.status(400).json({ error: "Invalid input: 'requests' must be an array." });
  }

  let results = [];

  for (let i = 0; i < requests.length; i++) {
    const item = requests[i];
    const { public_address, blockchain_id } = item || {};

    // بررسی اولیه ورودی هر آیتم
    if (!public_address || !blockchain_id) {
      results.push({
        public_address: public_address || null,
        blockchain_id: blockchain_id || null,
        error: "Missing 'public_address' or 'blockchain_id'"
      });
      continue;
    }

    // نام بلاک‌چین بر اساس عدد
    const blockchainName = getBlockchainName(blockchain_id);
    if (!blockchainName) {
      results.push({
        public_address,
        blockchain_id,
        error: "Invalid blockchain_id"
      });
      continue;
    }

    try {
      // واکشی تمام ارز/توکن‌های این بلاک‌چین از جدول Currencies
      const currencies = await Currencies.findAll({
        where: { BlockchainID: blockchain_id }
      });

      // تنها می‌خواهیم توکن‌ها را نمایش دهیم، پس کوین اصلی را نادیده می‌گیریم
      let tokensMap = {};

      // تابع کمکی برای واکشی بالانس توکن
      async function fetchTokenBalance(contractAddr, decimals) {
        const tokenApi = TOKEN_APIS[blockchainName];
        if (!tokenApi) {
          return 0; // بلاک‌چین ناشناخته در توکن
        }

        // ساخت URL با جای‌گذاری آدرس و کانترکت
        const apiUrl = tokenApi
          .replace("{public_address}", public_address)
          .replace("{contract_address}", contractAddr || "");

        // فراخوانی API
        const response = await axios.get(apiUrl);

        // برای بلاک‌چین‌هایی نظیر اتریوم، بایننس، پلیگان و ... معمولاً پاسخ در فیلد result نگهداری می‌شود
        let rawBalance = parseInt(response.data.result || "0");
        // تقسیم بر 10^DecimalPlaces برای تبدیل واحد
        let balance = rawBalance / (10 ** decimals);
        return balance;
      }

      // پردازش موازی تمام توکن‌های این بلاک‌چین
      const promises = [];
      for (let cur of currencies) {
        if (cur.IsToken) {
          let decimals = cur.DecimalPlaces || 18; // اگر خالی بود، پیش‌فرض 18
          const symbolKey = cur.Symbol || cur.SmartContractAddress;

          // ---- تغییر جدید: فقط زمانی مقدار بالانس را در tokensMap ذخیره کن که > 0 باشد
          const p = fetchTokenBalance(cur.SmartContractAddress, decimals)
            .then(val => {
              if (val > 0) {
                tokensMap[symbolKey] = val;
              }
            })
            .catch(err => {
              console.error(`Error fetching token balance for ${symbolKey}:`, err.message);
              // در صورت خطا، می‌توان تصمیم گرفت که 0 ثبت کنیم یا حذف کنیم
            });

          promises.push(p);
        }
      }

      // انتظار تا تمام درخواست‌های توکن انجام شوند
      await Promise.all(promises);

      // افزودن نتیجه‌ی این آدرس در آرایه‌ی خروجی
      results.push({
        public_address,
        blockchain_id,
        tokens: tokensMap
      });

    } catch (error) {
      console.error(`Error in /blockchain/batch for item index ${i} (public_address=${public_address}, blockchain_id=${blockchain_id}):`, error.message);
      results.push({
        public_address,
        blockchain_id,
        error: "Failed to fetch token balances"
      });
    }
  }

  return res.json({ results });
});

// ----------------------------------------------------------------------------
// اجرای سرور
// ----------------------------------------------------------------------------
app.listen(port, async () => {
  try {
    await sequelize.authenticate();
    console.log('Connection to MySQL has been established successfully.');
  } catch (err) {
    console.error('Unable to connect to the database:', err);
  }
  console.log(`Node.js server running at http://localhost:${port}`);
});
