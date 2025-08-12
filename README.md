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

---

## 💖 Support My Work

Your support helps me keep improving and building more tools like this 🚀

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/abedallahjoulany)


---

# 🛒 بوت تيليجرام للتسويق بالعمولة على AliExpress

**إنشاء روابط تسويق بالعمولة متعددة للحصول على أقصى الخصومات — تلقائيًا.**  

بوت تيليجرام مكتوب بلغة **بايثون** يكتشف روابط منتجات AliExpress في الرسائل، ويجلب تفاصيل المنتج من خلال واجهة برمجة تطبيقات التسويق بالعمولة لـ AliExpress، ثم يُنشئ **أنواعًا متعددة من روابط التسويق** (عروض العملات، العروض المميزة، العروض المجمّعة، التوفير الكبير) ويرسل رسالة منسقة تحتوي على صورة المنتج إن وُجدت.

---

## ✨ المميزات

- **الكشف التلقائي عن الروابط** – يراقب الرسائل بحثًا عن روابط منتجات AliExpress باستخدام الـ Regex.
- **تفاصيل المنتج** – يجلب عنوان المنتج، الصورة الرئيسية، وسعر البيع من خلال واجهة API الرسمية.
- **روابط تسويق متعددة** – يُنشئ روابط لـ:
  - 🪙 عروض العملات (Coin Offers)
  - 🔥 العروض المميزة (Super Deals)
  - ⏳ العروض المجمّعة (Bundle Offers)
  - 💰 التوفير الكبير (Big Save)
- **تكامل مع واجهة API الرسمية** – باستخدام `aliexpress.affiliate.productdetail.get` و `aliexpress.affiliate.link.generate`.
- **تكامل تيليجرام** – مبني باستخدام مكتبة `python-telegram-bot`.
- **رسائل منسقة** – يرسل تفاصيل المنتج مع صورة كتعليق HTML أو كنص منسق.
- **التخزين المؤقت** – كاش آمن ومتزامن لمدّة يوم افتراضيًا لتقليل استهلاك واجهة API.
- **معالجة غير متزامنة** – باستخدام `asyncio` و `ThreadPoolExecutor` لتسريع الاستجابة.
- **قابل للتخصيص** – من خلال ملف `.env` لإعداد مفاتيح API، رمز البوت، وإعدادات المنطقة.
- **تنظيف الكاش دوريًا** – يتم التنظيف يوميًا تلقائيًا عبر `JobQueue`.
- **تسجيل أساسي** – لمراقبة نشاط البوت والأخطاء.
- **روابط ثابتة أسفل الرسائل** – تشمل روابط مثل عروض Choice Day و Best Deals.

---

## 📦 المتطلبات

- **Python 3.8+**
- أداة `pip` لتثبيت الحزم
- أداة `git` لنسخ المستودع
- رمز بوت تيليجرام من [@BotFather](https://t.me/BotFather)
- بيانات API للتسويق بالعمولة من AliExpress:
  - App Key
  - App Secret
  - Tracking ID
- خادم أو جهاز لتشغيل البوت على مدار الساعة

---

## 🚀 التثبيت

```bash
# نسخ المستودع
git clone https://github.com/AbedJoulany/Aliexpress-Deals.git
cd Aliexpress-telegram-bot

# إنشاء بيئة عمل افتراضية
python -m venv venv
source venv/bin/activate  # على macOS/Linux
.env\Scriptsctivate   # على Windows

# تثبيت المتطلبات
pip install -r requirements.txt
```

---

## ⚙️ الإعداد

قم بإنشاء ملف `.env` في مجلد المشروع:

```env
# رمز بوت تيليجرام
TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN

# بيانات API لـ AliExpress
ALIEXPRESS_APP_KEY=YOUR_APP_KEY
ALIEXPRESS_APP_SECRET=YOUR_APP_SECRET
ALIEXPRESS_TRACKING_ID=YOUR_TRACKING_ID

# إعدادات المنطقة
TARGET_CURRENCY=USD
TARGET_LANGUAGE=en
QUERY_COUNTRY=US
```

---

## ▶️ تشغيل البوت

```bash
# تفعيل البيئة الافتراضية (إذا لم تكن مفعّلة)
source venv/bin/activate  # على macOS/Linux
.env\Scriptsctivate   # على Windows

# تشغيل البوت
python main.py
```

---

## 💡 الاستخدام

1. ابدأ محادثة مع البوت أو أضفه إلى مجموعة.
2. أرسل الأمر `/start` لاستقبال رسالة ترحيب.
3. أرسل أي رابط منتج من AliExpress:
   ```
   https://www.aliexpress.com/item/1234567890.html
   ```
4. سيقوم البوت بـ:
   - جلب تفاصيل المنتج
   - إنشاء روابط تسويق متعددة
   - إرسال رسالة منسقة مع صورة المنتج والعروض

---

## 🐳 النشر باستخدام Docker (اختياري)

```bash
# بناء الصورة
docker build -t aliexpress-telegram-bot .

# تشغيل الحاوية
docker run --env-file .env -d --name ali-telegram-bot aliexpress-telegram-bot
```

---

## 📚 الاعتمادات

- [`python-telegram-bot`](https://python-telegram-bot.org/) – للتعامل مع واجهة تيليجرام
- [`python-dotenv`](https://pypi.org/project/python-dotenv/) – لتحميل بيانات الإعداد من ملف `.env`
- [`aiohttp`](https://docs.aiohttp.org/) / `httpx` – عميل HTTP غير متزامن
- [`requests`](https://docs.python-requests.org/) – عميل HTTP متزامن
- `iop` – مكتبة الـ SDK الخاصة بـ AliExpress

---

## 📜 الترخيص

هذا المشروع مرخّص تحت [MIT License](LICENSE).

---

## 🌟 الدعم والترويج

إذا وجدت هذا المشروع مفيدًا:
- ⭐ ضع نجمة على المستودع
- انضم إلى بوت تيليجرام الخاص بنا للعروض الحية
- شاركه مع المطورين والمسوقين

---

## 💖 دعم مشاريعي

دعمك يساعدني على تطوير وتحسين المزيد من الأدوات 🚀  

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/abedallahjoulany)
