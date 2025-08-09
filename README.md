# 🛒 AliExpress Affiliate Telegram Bot

**Generate multiple affiliate links for maximum discounts — automatically.**  

A **Python-based Telegram bot** that detects AliExpress product links in messages, fetches product details via the AliExpress Affiliate API, and returns **multiple types of affiliate links** (Coin Offers, Super Deals, Bundle Offers, Big Save) in a neatly formatted message with product images.

---

## ✨ Features

- **Automatic Link Detection** – Monitors chats for AliExpress product URLs using regex.
- **Product Details** – Fetches product title, main image, and sale price via the official API.
- **Multiple Affiliate Links** – Generates links for:
  - 🪙 Coin Offers
  - 🔥 Super Deals
  - ⏳ Bundle Offers
  - 💰 Big Save
- **Official API Integration** – Uses `aliexpress.affiliate.productdetail.get` & `aliexpress.affiliate.link.generate` endpoints.
- **Telegram Integration** – Built using `python-telegram-bot`.
- **Formatted Responses** – Sends product details as a photo caption (HTML-formatted) or as text.
- **Caching** – Async-safe, time-based cache (default: 1 day) to minimize API calls.
- **Asynchronous Processing** – Uses `asyncio` and `ThreadPoolExecutor` for non-blocking API calls.
- **Configurable** – `.env` file for API keys, bot token, and regional settings.
- **Periodic Cache Cleanup** – Automatic daily cleanup using `JobQueue`.
- **Basic Logging** – Monitor bot activity & errors.
- **Static Links Footer** – Includes Choice Day, Best Deals, and other promos.

---

## 📦 Prerequisites

- **Python 3.8+**
- `pip` (Python package installer)
- `git` (for cloning the repository)
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- AliExpress Affiliate API credentials:
  - App Key
  - App Secret
  - Affiliate Tracking ID
- Server or hosting to run the bot 24/7

---

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/AbedJoulany/Aliexpress-Deals.git
cd Aliexpress-telegram-bot

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
.env\Scriptsctivate   # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## ⚙️ Configuration

Create a `.env` file in the project root:

```env
# Telegram Bot Token
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN

# AliExpress API Credentials
ALIEXPRESS_APP_KEY=YOUR_APP_KEY
ALIEXPRESS_APP_SECRET=YOUR_APP_SECRET
ALIEXPRESS_TRACKING_ID=YOUR_TRACKING_ID

# Regional Settings
TARGET_CURRENCY=USD
TARGET_LANGUAGE=en
QUERY_COUNTRY=US
```

---

## ▶️ Running the Bot

```bash
# Activate venv (if not active)
source venv/bin/activate  # macOS/Linux
.env\Scriptsctivate   # Windows

# Run
python main.py
```

---

## 💡 Usage

1. Start a chat with your bot or add it to a group.
2. Send `/start` to get a welcome message.
3. Send any AliExpress product link:
   ```
   https://www.aliexpress.com/item/1234567890.html
   ```
4. The bot will:
   - Fetch product details
   - Generate multiple affiliate links
   - Send a formatted message with product image & offers

---

## 🐳 Docker Deployment (Optional)

```bash
# Build image
docker build -t aliexpress-telegram-bot .

# Run container
docker run --env-file .env -d --name ali-telegram-bot aliexpress-telegram-bot
```

---

## 📚 Dependencies

- [`python-telegram-bot`](https://python-telegram-bot.org/) – Telegram API integration
- [`python-dotenv`](https://pypi.org/project/python-dotenv/) – Environment variable loading
- [`aiohttp`](https://docs.aiohttp.org/) / `httpx` – Async HTTP clients
- [`requests`](https://docs.python-requests.org/) – Synchronous HTTP client
- `iop` – Alibaba/AliExpress API SDK

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

---

## 🌟 Support & Promotion

If you find this project useful:
- ⭐ Star this repository
- Join our Telegram bot for live deals
- Share it with fellow developers and affiliate marketers
