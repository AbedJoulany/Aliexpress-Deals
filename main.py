# main.py
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

from cache_manager import CacheManager
from aliexpress_client import AliExpressClient
from url_processor import URLProcessor
from telegram_bot import TelegramBot

# --- Basic Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.INFO)


def main() -> None:
    load_dotenv()

    telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    aliexpress_app_key = os.getenv('ALIEXPRESS_APP_KEY')
    aliexpress_app_secret = os.getenv('ALIEXPRESS_APP_SECRET')
    target_currency = os.getenv('TARGET_CURRENCY', 'USD')
    target_language = os.getenv('TARGET_LANGUAGE', 'en')
    query_country = os.getenv('QUERY_COUNTRY', 'IL')
    aliexpress_tracking_id = os.getenv('ALIEXPRESS_TRACKING_ID', 'bot')
    cache_expiry_days = int(os.getenv('CACHE_EXPIRY_DAYS',
                                      '1'))  # Default to 1 day

    if not all([
            telegram_bot_token, aliexpress_app_key, aliexpress_app_secret,
            aliexpress_tracking_id
    ]):
        logger.error(
            "Error: Missing required environment variables. Check TELEGRAM_BOT_TOKEN, ALIEXPRESS_*, TRACKING_ID."
        )
        exit()

    # Thread pool for blocking API calls and scraping
    executor = ThreadPoolExecutor(max_workers=10)

    try:
        cache_manager = CacheManager(cache_expiry_days=cache_expiry_days)
        aliexpress_client = AliExpressClient(
            app_key=aliexpress_app_key,
            app_secret=aliexpress_app_secret,
            tracking_id=aliexpress_tracking_id,
            target_currency=target_currency,
            target_language=target_language,
            query_country=query_country,
            executor=executor,
            cache_manager=cache_manager)
        url_processor = URLProcessor(query_country=query_country,
                                     cache_manager=cache_manager)

        telegram_bot = TelegramBot(token=telegram_bot_token,
                                   aliexpress_client=aliexpress_client,
                                   url_processor=url_processor,
                                   cache_manager=cache_manager,
                                   executor=executor)
        telegram_bot.run()
    except Exception as e:
        logger.critical(
            f"Fatal error during bot initialization or runtime: {e}")
    finally:
        logger.info("Shutting down thread pool...")
        executor.shutdown(wait=True)
        logger.info("Thread pool shut down.")


if __name__ == "__main__":
    main()
