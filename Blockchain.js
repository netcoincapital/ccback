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
const fs = require('fs');
const path = require('path');

const app = express();
const port = 4000;
app.use(express.json());

// ----------------------------------------------------------------------------
// تنظیمات لاگینگ: ایجاد پوشه Logy و فایل لاگ جدید در هر اجرا
// ----------------------------------------------------------------------------
const logDir = path.join(__dirname, 'Logy');
if (!fs.existsSync(logDir)) {
  fs.mkdirSync(logDir, { recursive: true });
}
function getCurrentTimestamp() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  return `${year}-${month}-${day}_${hours}-${minutes}-${seconds}`;
}
const logFileName = `blockchain_log_${getCurrentTimestamp()}.log`;
const logFilePath = path.join(logDir, logFileName);

function log(message) {
  const logMessage = `${new Date().toISOString()} - ${message}\n`;
  fs.appendFileSync(logFilePath, logMessage);
}

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


const API_KEYS = {
    ETHERSCAN: process.env.ETHERSCAN_API_KEY,
    BSCSCAN: process.env.BSCSCAN_API_KEY,
    POLYGONSCAN: process.env.POLYGONSCAN_API_KEY,
    ARBITRUMSCAN: process.env.ARBITRUMSCAN_API_KEY,
    TRONGRID: process.env.TRONGRID_API_KEY,
    SOLANA_RPC: process.env.SOLANA_RPC_URL,
    AVALANCHE_API_KEY: process.env.AVALANCHE_API_KEY,
    BLOCKCYPHER: process.env.BLOCKCYPHER_API_KEY,
    RIPPLE_API_KEY: process.env.RIPPLE_API_KEY,
    POLKADOT_API_KEY: process.env.POLKADOT_API_KEY
};


const BLOCKCHAIN_APIS = {
    "Bitcoin": {
        url: `https://api.blockcypher.com/v1/btc/main/addrs/{public_address}/balance?token=${API_KEYS.BLOCKCYPHER}`,
        processResponse: (response) => {
            return response.data.balance / 1e8; // تبدیل ساتوشی به بیتکوین
        }
    },
    "Ethereum": {
        url: `https://api.etherscan.io/api?module=account&action=balance&address={public_address}&tag=latest&apikey=${API_KEYS.ETHERSCAN}`,
        processResponse: (response) => {
            return parseInt(response.data.result) / 1e18; // تبدیل Wei به ETH
        }
    },
    "Tron": {
        url: "https://api.trongrid.io/v1/accounts/{public_address}",
        headers: { 'TRON-PRO-API-KEY': API_KEYS.TRONGRID },
        processResponse: (response) => {
            return response.data.balance / 1e6; // تبدیل Sun به TRX
        }
    },
    "Binance": {
        url: `https://api.bscscan.com/api?module=account&action=balance&address={public_address}&tag=latest&apikey=${API_KEYS.BSCSCAN}`,
        processResponse: (response) => {
            return parseInt(response.data.result) / 1e18; // تبدیل Wei به BNB
        }
    },
    "Polygon": {
        url: `https://api.polygonscan.com/api?module=account&action=balance&address={public_address}&tag=latest&apikey=${API_KEYS.POLYGONSCAN}`,
        processResponse: (response) => {
            return parseInt(response.data.result) / 1e18; // تبدیل Wei به MATIC
        }
    },
    "XRP": {
        url: "https://data.ripple.com/v2/accounts/{public_address}/balances",
        headers: { 'Authorization': `Bearer ${API_KEYS.RIPPLE_API_KEY}` },
        processResponse: (response) => {
            const balance = response.data.balances.find(b => b.currency === 'XRP');
            return balance ? parseFloat(balance.value) : 0;
        }
    },
    "Solana": {
        url: API_KEYS.SOLANA_RPC,
        method: 'POST',
        processRequest: (address) => ({
            jsonrpc: '2.0',
            id: 1,
            method: 'getBalance',
            params: [address]
        }),
        processResponse: (response) => {
            return response.data.result.value / 1e9; // تبدیل Lamports به SOL
        }
    },
    "Arbitrum": {
        url: `https://api.arbiscan.io/api?module=account&action=balance&address={public_address}&tag=latest&apikey=${API_KEYS.ARBITRUMSCAN}`,
        processResponse: (response) => {
            return parseInt(response.data.result) / 1e18;
        }
    },
    "Polkadot": {
        url: `https://polkadot.api.subscan.io/api/scan/account/tokens`,
        headers: { 'X-API-Key': API_KEYS.POLKADOT_API_KEY },
        method: 'POST',
        processRequest: (address) => ({
            address: address
        }),
        processResponse: (response) => {
            return parseFloat(response.data.data.native) / 1e10;
        }
    },
    "Avalanche": {
        url: `https://api.snowtrace.io/api?module=account&action=balance&address={public_address}&tag=latest&apikey=${API_KEYS.AVALANCHE_API_KEY}`,
        processResponse: (response) => {
            return parseInt(response.data.result) / 1e18;
        }
    }
};

// تنظیمات API های توکن
const TOKEN_APIS = {
    "Ethereum": {
        url: `https://api.etherscan.io/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={public_address}&tag=latest&apikey=${API_KEYS.ETHERSCAN}`,
        processResponse: (response, decimals) => {
            return parseInt(response.data.result) / (10 ** decimals);
        }
    },
    "Tron": {
        url: "https://api.trongrid.io/v1/accounts/{public_address}",
        headers: { 'TRON-PRO-API-KEY': API_KEYS.TRONGRID },
        processResponse: (response, contractAddress, decimals) => {
            const trc20Tokens = response.data.trc20;
            if (!trc20Tokens || !trc20Tokens[contractAddress]) return 0;
            return parseInt(trc20Tokens[contractAddress]) / (10 ** decimals);
        }
    },
    "Binance": {
        url: `https://api.bscscan.com/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={public_address}&tag=latest&apikey=${API_KEYS.BSCSCAN}`,
        processResponse: (response, decimals) => {
            return parseInt(response.data.result) / (10 ** decimals);
        }
    },
    "Polygon": {
        url: `https://api.polygonscan.com/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={public_address}&tag=latest&apikey=${API_KEYS.POLYGONSCAN}`,
        processResponse: (response, decimals) => {
            return parseInt(response.data.result) / (10 ** decimals);
        }
    },
    "XRP": {
        url: "https://data.ripple.com/v2/accounts/{public_address}/balances",
        headers: { 'Authorization': `Bearer ${API_KEYS.RIPPLE_API_KEY}` },
        processResponse: (response, contractAddress) => {
            const token = response.data.balances.find(b => b.currency === contractAddress);
            return token ? parseFloat(token.value) : 0;
        }
    },
    "Solana": {
        url: API_KEYS.SOLANA_RPC,
        method: 'POST',
        processRequest: (address, contractAddress) => ({
            jsonrpc: '2.0',
            id: 1,
            method: 'getTokenAccountsByOwner',
            params: [
                address,
                { mint: contractAddress },
                { encoding: 'jsonParsed' }
            ]
        }),
        processResponse: (response, decimals) => {
            if (!response.data.result.value.length) return 0;
            return parseInt(response.data.result.value[0].account.data.parsed.info.tokenAmount.amount) / (10 ** decimals);
        }
    },
    "Arbitrum": {
        url: `https://api.arbiscan.io/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={public_address}&tag=latest&apikey=${API_KEYS.ARBITRUMSCAN}`,
        processResponse: (response, decimals) => {
            return parseInt(response.data.result) / (10 ** decimals);
        }
    },
    "Polkadot": {
        url: `https://polkadot.api.subscan.io/api/scan/account/tokens`,
        headers: { 'X-API-Key': API_KEYS.POLKADOT_API_KEY },
        method: 'POST',
        processRequest: (address) => ({
            address: address
        }),
        processResponse: (response, contractAddress, decimals) => {
            const token = response.data.data.tokens.find(t => t.token_id === contractAddress);
            return token ? parseFloat(token.balance) / (10 ** decimals) : 0;
        }
    },
    "Avalanche": {
        url: `https://api.snowtrace.io/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={public_address}&tag=latest&apikey=${API_KEYS.AVALANCHE_API_KEY}`,
        processResponse: (response, decimals) => {
            return parseInt(response.data.result) / (10 ** decimals);
        }
    }
};

// تابع کمکی برای جایگزینی پارامترها در URL
function replaceUrlParams(url, params) {
    let result = url;
    for (const [key, value] of Object.entries(params)) {
        result = result.replace(`{${key}}`, value);
    }
    return result;
}

// -----------------------------------------------------------------------------
// تابع اصلی دریافت موجودی توکن (برای توکن‌های هوشمند)
// -----------------------------------------------------------------------------
async function fetchTokenBalance(contractAddr, decimals, blockchainName, public_address) {
    const api = TOKEN_APIS[blockchainName];
    if (!api) {
        throw new Error(`Unsupported blockchain: ${blockchainName}`);
    }

    try {
        const config = {
            method: api.method || 'GET',
            url: replaceUrlParams(api.url, {
                public_address: public_address,
                contract_address: contractAddr
            }),
            headers: api.headers || {}
        };

        if (api.processRequest) {
            config.data = api.processRequest(public_address, contractAddr);
        }

        const response = await axios(config);
        return api.processResponse(response, contractAddr, decimals);
    } catch (error) {
        console.error(`Error fetching token balance for ${blockchainName}:`, error);
        log(`Error fetching token balance for ${blockchainName} (address: ${public_address}): ${error.message}`);
        return 0;
    }
}

// -----------------------------------------------------------------------------
// تابع دریافت موجودی اصلی بلاکچین
// -----------------------------------------------------------------------------
async function fetchNativeBalance(blockchainName, public_address) {
    const api = BLOCKCHAIN_APIS[blockchainName];
    if (!api) {
        throw new Error(`Unsupported blockchain: ${blockchainName}`);
    }

    try {
        const config = {
            method: api.method || 'GET',
            url: replaceUrlParams(api.url, { public_address: public_address }),
            headers: api.headers || {}
        };

        if (api.processRequest) {
            config.data = api.processRequest(public_address);
        }

        const response = await axios(config);
        return api.processResponse(response);
    } catch (error) {
        console.error(`Error fetching native balance for ${blockchainName}:`, error);
        log(`Error fetching native balance for ${blockchainName} (address: ${public_address}): ${error.message}`);
        return 0;
    }
}

// -----------------------------------------------------------------------------
// تبدیل عدد BlockchainID به نام بلاک‌چین
// -----------------------------------------------------------------------------
function getBlockchainName(blockchainId) {
  // جدول نگاشت؛ بسته به دیتابیس شما تغییر کند
  const mapping = {
    4: "Bitcoin",
    1: "Ethereum",
    2: "Tron",
    3: "Binance",
    5: "Polygon",
    11: "XRP",
    12: "Solana",
    6: "Arbitrum",
    13: "Polkadot",
    14: "Avalanche"
  };
  return mapping[blockchainId];
}

// -----------------------------------------------------------------------------
// Endpoint: /blockchain/batch (نسخه Batch واقعی)
// -----------------------------------------------------------------------------
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
  log(`Received /blockchain/batch request: ${JSON.stringify(req.body)}`);

  const { requests } = req.body;

  if (!requests || !Array.isArray(requests)) {
    log(`Invalid input received: ${JSON.stringify(req.body)}`);
    return res.status(400).json({ error: "Invalid input: 'requests' must be an array." });
  }

  let results = [];

  for (let i = 0; i < requests.length; i++) {
    const item = requests[i];
    const { public_address, blockchain_id } = item || {};

    // بررسی اولیه ورودی هر آیتم
    if (!public_address || !blockchain_id) {
      log(`Request missing public_address or blockchain_id: ${JSON.stringify(item)}`);
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
      log(`Invalid blockchain_id for address ${public_address}: ${blockchain_id}`);
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

      // تابع کمکی برای واکشی بالانس توکن (تعریف توابع محلی برای پردازش توکن‌ها)
      async function fetchTokenBalance(contractAddr, decimals) {
        const tokenApi = TOKEN_APIS[blockchainName];
        if (!tokenApi) {
          return 0; // بلاک‌چین ناشناخته در توکن
        }

        // ساخت URL با جای‌گذاری آدرس و کانترکت
        const apiUrl = tokenApi.url
          .replace("{public_address}", public_address)
          .replace("{contract_address}", contractAddr || "");

        try {
          const response = await axios.get(apiUrl);
          let rawBalance = parseInt(response.data.result || "0");
          let balance = rawBalance / (10 ** decimals);
          return balance;
        } catch (err) {
          console.error(`Error fetching token balance for ${contractAddr}:`, err.message);
          log(`Error fetching token balance for ${contractAddr} (address: ${public_address}): ${err.message}`);
          return 0;
        }
      }

      // پردازش موازی تمام توکن‌های این بلاک‌چین
      const promises = [];
      for (let cur of currencies) {
        if (cur.IsToken) {
          let decimals = cur.DecimalPlaces || 18; // اگر خالی بود، پیش‌فرض 18
          const symbolKey = cur.Symbol || cur.SmartContractAddress;

          // تغییر: فقط زمانی مقدار بالانس را در tokensMap ذخیره کن که > 0 باشد
          const p = fetchTokenBalance(cur.SmartContractAddress, decimals)
            .then(val => {
              if (val > 0) {
                tokensMap[symbolKey] = val;
              }
            })
            .catch(err => {
              console.error(`Error fetching token balance for ${symbolKey}:`, err.message);
              log(`Error fetching token balance for ${symbolKey} (address: ${public_address}): ${err.message}`);
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
      log(`Error in /blockchain/batch for item index ${i} (public_address=${public_address}, blockchain_id=${blockchain_id}): ${error.message}`);
      results.push({
        public_address,
        blockchain_id,
        error: "Failed to fetch token balances"
      });
    }
  }

  log(`Responding with results: ${JSON.stringify({ results })}`);
  return res.json({ results });
});


app.listen(port, async () => {
  try {
    await sequelize.authenticate();
    console.log('Connection to MySQL has been established successfully.');
    log('Connection to MySQL has been established successfully.');
  } catch (err) {
    console.error('Unable to connect to the database:', err);
    log(`Unable to connect to the database: ${err.message}`);   
  }
  console.log(`Node.js server running at http://localhost:${port}`);
  log(`Server started at http://localhost:${port}`);
});

// کلاس خطای سفارشی
class BlockchainError extends Error {
    constructor(message, code, details) {
        super(message);
        this.code = code;
        this.details = details;
    }
}

// مدیریت خطا با retry
async function fetchWithRetry(fn, retries = 3) {
    for (let i = 0; i < retries; i++) {
        try {
            return await fn();
        } catch (error) {
            if (i === retries - 1) throw error;
            await new Promise(r => setTimeout(r, 1000 * Math.pow(2, i)));
        }
    }
}
