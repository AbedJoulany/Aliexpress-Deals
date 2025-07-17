import logging
import re
import asyncio
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, JobQueue
from telegram.constants import ParseMode, ChatAction

from aliexpress_client import AliExpressClient
from url_processor import URLProcessor
from cache_manager import CacheManager
from constants import OFFER_PARAMS, OFFER_ORDER
from aliexpress_utils import get_product_details_by_id  # Added this import as it was used

logger = logging.getLogger(__name__)
# رمز RTL لإجبار النص على الاتجاه من اليمين لليسار
rtl_mark = "\u200F"
ARABIC_CURRENCY_NAMES = {
    "USD": "دولار أمريكي",
    "SAR": "ريال سعودي",
    "AED": "درهم إماراتي",
    "EGP": "جنيه مصري",
    "EUR": "يورو",
    "GBP": "جنيه إسترليني",
    "CNY": "يوان صيني",
    "ILS": "شيكل إسرائيلي",
}


class TelegramBot:

    def __init__(self, token: str, aliexpress_client: AliExpressClient,
                 url_processor: URLProcessor, cache_manager: CacheManager,
                 executor: ThreadPoolExecutor):
        self.token = token
        self.aliexpress_client = aliexpress_client
        self.url_processor = url_processor
        self.cache_manager = cache_manager
        self.executor = executor
        self.application = Application.builder().token(self.token).build()
        self._setup_handlers()

    def _setup_handlers(self):
        """Sets up all Telegram command and message handlers."""
        self.application.add_handler(CommandHandler("start", self.start))

        combined_domain_regex = re.compile(
            r'aliexpress\.com|s\.click\.aliexpress\.com|a\.aliexpress\.com',
            re.IGNORECASE)

        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND
                & filters.Regex(combined_domain_regex), self.handle_message))

        self.application.add_handler(
            MessageHandler(
                filters.FORWARDED & filters.TEXT
                & filters.Regex(combined_domain_regex), self.handle_message))

        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND
                & ~filters.Regex(combined_domain_regex), self.no_link_message))

        job_queue = self.application.job_queue
        # Initial run of cache cleanup, then schedule repeating
        job_queue.run_once(self.cache_manager.periodic_cache_cleanup,
                           60)  # Run after 60 seconds
        job_queue.run_repeating(
            self.cache_manager.periodic_cache_cleanup,
            interval=timedelta(days=1),  # Every 24 hours
            first=timedelta(days=1))  # Start after first day

    async def start(self, update: Update,
                    context: ContextTypes.DEFAULT_TYPE) -> None:
        """Sends a welcome message when the /start command is issued."""
        await update.message.reply_html(
            "👋 مرحبًا بك في بوت خصومات علي إكسبريس! 🛍️\n\n"
            "🔍 <b>كيفية استخدام البوت:</b>\n"
            "1️⃣ انسخ رابط منتج من موقع AliExpress 📋\n"
            "2️⃣ أرسل الرابط إلى هذا البوت 📤\n"
            "3️⃣ سيقوم البوت تلقائيًا بإنشاء روابط الخصم ✨\n"
            "🔗 <b>أنواع الروابط المدعومة:</b>\n"
            "• روابط المنتجات العادية من AliExpress 🌐\n"
            "• روابط AliExpress المختصرة 🔄\n\n"
            "🚀 أرسل أي رابط منتج الآن لتجربة البوت! 🎁")

    async def no_link_message(self, update: Update,
                              context: ContextTypes.DEFAULT_TYPE) -> None:
        """Responds when no AliExpress link is found in the message."""
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=
            "📭 الرجاء إرسال رابط منتج من موقع AliExpress حتى نتمكن من إنشاء روابط الخصم 💡"
        )

    async def _fetch_product_info(self, product_id: str):
        """Fetches product details from API, with scraping fallback."""
        product_details = await self.aliexpress_client.fetch_product_details(
            product_id)

        if product_details:
            logger.info(
                f"Successfully fetched details via API for product ID: {product_id}"
            )
            return {
                'image_url': product_details.get('image_url'),
                'price': product_details.get('price'),
                'currency': product_details.get('currency', ''),
                'title': product_details.get('title', f"Product {product_id}"),
                'source': "API"
            }
        else:
            logger.warning(
                f"API failed for product ID: {product_id}. Attempting scraping fallback."
            )
            try:
                scraped_name, scraped_image = await asyncio.get_event_loop(
                ).run_in_executor(
                    self.executor,
                    lambda: get_product_details_by_id(product_id))
                if scraped_name:
                    logger.info(
                        f"Successfully scraped details for product ID: {product_id}"
                    )
                    return {
                        'image_url': scraped_image,
                        'price': None,  # Price not available from scraping
                        'currency': '',
                        'title': scraped_name,
                        'source': "Scraped"
                    }
                else:
                    logger.warning(
                        f"Scraping also failed for product ID: {product_id}")
                    return {'source': "None", 'title': f"Product {product_id}"}
            except Exception as scrape_err:
                logger.error(
                    f"Error during scraping fallback for product ID {product_id}: {scrape_err}"
                )
                return {'source': "None", 'title': f"Product {product_id}"}

    def _generate_offer_urls(self, base_url: str, product_id: str):
        """Builds target URLs for different offer strategies."""
        target_urls_map = {}
        all_urls_to_fetch = []
        for offer_key in OFFER_ORDER:
            offer_strategy_instance = OFFER_PARAMS[offer_key]
            offer_urls = offer_strategy_instance.build_urls(
                base_url, product_id)
            logger.debug(f"Generated URLs for offer {offer_key}: {offer_urls}")
            target_urls_map[offer_key] = offer_urls
            all_urls_to_fetch.extend(offer_urls)

        # Return the wrapped URLs
        return target_urls_map, all_urls_to_fetch

    async def _generate_and_map_affiliate_links(self, all_urls_to_fetch: list):
        """Generates batch affiliate links and maps them to offer keys."""
        logger.info(
            f"Requesting batch affiliate links for {len(all_urls_to_fetch)} URLs."
        )
        all_links_dict = await self.aliexpress_client.generate_affiliate_links_batch(
            all_urls_to_fetch)
        return all_links_dict

    def _format_response_message(self, product_info: dict,
                                 generated_links: dict):
        """تهيئة نص الرسالة لإرسالها عبر تيليجرام باللغة العربية."""
        product_title = product_info.get('title')
        product_price = product_info.get('price')
        product_currency = product_info.get('currency')
        details_source = product_info.get('source')

        message_lines = []
        message_lines.append(f"<b>{rtl_mark}{product_title[:250]}</b>")

        arabic_currency = ARABIC_CURRENCY_NAMES.get(product_currency, product_currency)

        if details_source == "API" and product_price:
            price_str = f"{product_price} {arabic_currency}".strip()
            message_lines.append(f"\n<b>السعر بعد الخصم:</b> {price_str}\n")
        elif details_source == "Scraped":
            message_lines.append("\n<b>السعر بعد الخصم:</b> غير متوفر\n")
        else:
            message_lines.append("\n<b>تفاصيل المنتج غير متوفرة</b>\n")

        message_lines.append("<b>العروض المتاحة:</b>")

        for offer_key in OFFER_ORDER:
            link = generated_links.get(offer_key)
            offer_name = OFFER_PARAMS[offer_key].label
            if link:
                message_lines.append(
                    f'{offer_name}: <a href="{link}">اضغط هنا</a>')
            else:
                message_lines.append(f"{offer_name}: ❌ فشل في الإنشاء")

        message_lines.append("\n<i>تم الإنشاء بواسطة P4uDeals</i>")
        return "\n".join(message_lines)

    def _create_inline_keyboard(self):
        """Creates the standard inline keyboard markup."""
        keyboard = [
            [
                InlineKeyboardButton(
                    "Choice Day",
                    url="https://s.click.aliexpress.com/e/_oC3lwzi"),
                InlineKeyboardButton(
                    "Big Save",
                    url="https://s.click.aliexpress.com/e/_om2vvDO")
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    async def _send_product_message(self, chat_id: int, response_text: str,
                                    product_image: str | None,
                                    reply_markup: InlineKeyboardMarkup):
        """Sends the final product message (with or without image)."""
        try:
            if product_image:
                await self.application.bot.send_photo(
                    chat_id=chat_id,
                    photo=product_image,
                    caption=response_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup)
            else:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=response_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup)
        except Exception as send_error:
            logger.error(
                f"Failed to send message with keyboard for chat {chat_id}: {send_error}"
            )
            # Fallback to sending text-only message if photo fails
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=
                f"⚠️ حدث خطأ أثناء إرسال الرسالة. إليك العروض المتوفرة:\n\n{response_text}",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=reply_markup)

    async def process_product_telegram(self, product_id: str, base_url: str,
                                       update: Update,
                                       context: ContextTypes.DEFAULT_TYPE):
        """Fetches details, generates links, and sends a formatted message to Telegram."""
        chat_id = update.effective_chat.id
        logger.info(f"Processing Product ID: {product_id} for chat {chat_id}")

        try:
            # Step 1: Fetch Product Info (API or Scraping)
            product_info = await self._fetch_product_info(product_id)
            product_title = product_info.get('title', f"Product {product_id}")
            product_image = product_info.get('image_url')

            # Step 2: Generate Offer URLs
            target_urls_map, all_urls_to_fetch = self._generate_offer_urls(
                base_url, product_id)

            logger.debug(
                f"DEBUG: all_urls_to_fetch for product {product_id}: {all_urls_to_fetch}"
            )

            # Step 3: Generate Batch Affiliate Links
            all_links_dict = await self._generate_and_map_affiliate_links(
                all_urls_to_fetch)

            logger.debug(
                f"DEBUG: all_links_dict received for product {product_id}: {all_links_dict}"
            )

            # Map generated links back to offer keys
            generated_links = {}
            success_count = 0
            for offer_key in OFFER_ORDER:
                logger.debug(
                    f"DEBUG: Processing offer_key: {offer_key} for product {product_id}"
                )
                # urls_for_offer now contains wrapped URLs
                urls_for_offer = target_urls_map.get(offer_key, [])
                logger.debug(
                    f"DEBUG: URLs for offer '{offer_key}' (WRAPPED): {urls_for_offer}"
                )

                found_link_for_offer = False
                # Since each strategy returns a list with one URL, this loop runs once.
                # 'url' here is the WRAPPED target URL
                for url in urls_for_offer:
                    logger.debug(
                        f"DEBUG: Checking URL '{url}' in all_links_dict for offer '{offer_key}'"
                    )
                    link = all_links_dict.get(
                        url)  # Lookup using the wrapped URL
                    if link:  # 'link' will be the final wrapped affiliate link
                        generated_links[offer_key] = link
                        success_count += 1
                        found_link_for_offer = True
                        logger.debug(
                            f"DEBUG: Found link for offer '{offer_key}': {link}. Success count: {success_count}"
                        )
                        break

                if not found_link_for_offer:
                    generated_links[offer_key] = None
                    logger.warning(
                        f"Failed to get affiliate link for offer {offer_key} (target: {target_urls_map.get(offer_key)}) for product {product_id}"
                    )
                    logger.debug(
                        f"DEBUG: No link found for offer '{offer_key}'. generated_links updated: {generated_links}"
                    )

            logger.debug(
                f"DEBUG: Final generated_links for product {product_id}: {generated_links}"
            )
            logger.debug(
                f"DEBUG: Total successful links for product {product_id}: {success_count}"
            )

            # Step 4: Format Response Message
            response_text = self._format_response_message(
                product_info, generated_links)
            # Step 5: Create Inline Keyboard
            reply_markup = self._create_inline_keyboard()

            # Step 6: Send Message to Telegram
            if success_count > 0:
                await self._send_product_message(chat_id, response_text,
                                                 product_image, reply_markup)
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=
                    f"<b>{product_title[:250]}</b>\n\nلم نتمكن من العثور على عروض لهذا المنتج حاليًا ❌",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup)

        except Exception as e:
            logger.exception(
                f"Unhandled error processing product {product_id} in chat {chat_id}: {e}"
            )
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=
                    f"حدث خطأ غير متوقع أثناء معالجة المنتج برقم {product_id}. نأسف على ذلك 😢"
                )
            except Exception:
                logger.error(
                    f"Failed to send error message for product {product_id} to chat {chat_id}"
                )

    async def _send_loading_animation(self, chat_id: int):
        """Sends a loading sticker animation."""
        return await self.application.bot.send_sticker(
            chat_id,
            "CAACAgIAAxkBAAIU1GYOk5jWvCvtykd7TZkeiFFZRdUYAAIjAAMoD2oUJ1El54wgpAY0BA"
        )

    async def _delete_loading_animation(self, chat_id: int, message_id: int):
        """Deletes a loading sticker animation."""
        try:
            await self.application.bot.delete_message(chat_id, message_id)
        except Exception as delete_err:
            logger.warning(f"Could not delete loading sticker: {delete_err}")

    async def _extract_and_process_urls(self, message_text: str,
                                        update: Update,
                                        context: ContextTypes.DEFAULT_TYPE):
        """Extracts and validates AliExpress URLs from message text."""
        chat_id = update.effective_chat.id
        potential_urls = self.url_processor.extract_potential_aliexpress_urls(
            message_text)

        if not potential_urls:
            await context.bot.send_message(
                chat_id=chat_id,
                text=
                "❌ لم يتم العثور على أي روابط AliExpress في رسالتك. الرجاء إرسال رابط منتج صحيح 🔗"
            )
            return []  # Return empty list if no URLs are found

        logger.info(
            f"Found {len(potential_urls)} potential URLs in message from {update.effective_user.username or update.effective_user.id} in chat {chat_id}"
        )
        return potential_urls

    async def _resolve_and_prepare_product_tasks(
            self, potential_urls: list, update: Update,
            context: ContextTypes.DEFAULT_TYPE):
        """Resolves short links, extracts product IDs, and prepares tasks."""
        processed_product_ids = set()
        tasks = []
        async with aiohttp.ClientSession() as session:
            for url in potential_urls:
                original_url = url
                product_id = None
                base_url = None

                if not url.startswith(('http://', 'https://')):
                    if re.match(
                            r'^(?:www\.|s\.click\.|a\.)?[\w-]*aliexpress\.(?:com|ru|es|fr|pt|it|pl|nl|co\.kr|co\.jp|com\.br|com\.tr|com\.vn|id|th|ar)',
                            url, re.IGNORECASE):
                        logger.debug(
                            f"Prepending https:// to potential URL: {url}")
                        url = f"https://{url}"
                    else:
                        logger.debug(
                            f"Skipping potential URL without scheme or known AE domain: {original_url}"
                        )
                        continue

                if self.url_processor.STANDARD_ALIEXPRESS_DOMAIN_REGEX.match(
                        url):
                    product_id = self.url_processor.extract_product_id(url)
                    if product_id:
                        base_url = self.url_processor.clean_aliexpress_url(
                            url, product_id)
                        logger.info(
                            f"Found standard URL: {url} -> ID: {product_id}, Base: {base_url}"
                        )
                elif self.url_processor.SHORT_LINK_DOMAIN_REGEX.match(url):
                    logger.debug(f"Found potential short link: {url}")
                    final_url = await self.url_processor.resolve_short_link(
                        url, session)
                    if final_url:
                        product_id = self.url_processor.extract_product_id(
                            final_url)
                        if product_id:
                            base_url = self.url_processor.clean_aliexpress_url(
                                final_url, product_id)
                            logger.debug(
                                f"Resolved short link: {url} -> {final_url} -> ID: {product_id}, Base: {base_url}"
                            )
                        else:
                            logger.warning(
                                f"Could not extract product ID from resolved short link: {final_url}"
                            )
                    else:
                        logger.warning(
                            f"Could not resolve short link: {original_url}")

                if product_id and base_url and product_id not in processed_product_ids:
                    processed_product_ids.add(product_id)
                    tasks.append(
                        self.process_product_telegram(product_id, base_url,
                                                      update, context))
                elif product_id and product_id in processed_product_ids:
                    logger.debug(
                        f"Skipping duplicate product ID: {product_id}")
        return tasks

    async def handle_message(self, update: Update,
                             context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles incoming text messages, extracts URLs, and processes them."""
        if not update.message or not update.message.text:
            return

        message_text = update.message.text
        user = update.effective_user
        chat_id = update.effective_chat.id

        is_forwarded = update.message.forward_origin is not None
        if is_forwarded:
            origin_info = f" (originally from {update.message.forward_origin.sender_user.username})" if hasattr(
                update.message.forward_origin, 'sender_user') else ""
            logger.info(
                f"Processing forwarded message from {user.username or user.id} in chat {chat_id}{origin_info}"
            )

        # Step 1: Extract and Validate URLs
        potential_urls = await self._extract_and_process_urls(
            message_text, update, context)
        if not potential_urls:
            return  # _extract_and_process_urls already sends an error message

        # Step 2: Send Loading Animation
        await context.bot.send_chat_action(chat_id=chat_id,
                                           action=ChatAction.TYPING)
        loading_animation = await self._send_loading_animation(chat_id)

        # Step 3: Resolve URLs and Prepare Product Tasks
        tasks = await self._resolve_and_prepare_product_tasks(
            potential_urls, update, context)

        if not tasks:
            logger.info(
                f"No processable AliExpress product links found after filtering/resolution in message from {user.username or user.id}"
            )
            await context.bot.send_message(
                chat_id=chat_id,
                text=
                "❌ لم نتمكن من العثور على أي روابط منتجات صالحة من AliExpress في هذه الرسالة ❌"
            )
            await self._delete_loading_animation(chat_id,
                                                 loading_animation.message_id)
            return

        if len(tasks) > 1:
            await context.bot.send_message(
                chat_id=chat_id,
                text=
                f"⏳ جاري معالجة {len(tasks)} منتج من AliExpress من رسالتك. الرجاء الانتظار..."
            )

        logger.info(
            f"Processing {len(tasks)} unique AliExpress products for chat {chat_id}"
        )
        await asyncio.gather(*tasks)

        # Step 4: Delete Loading Animation
        await self._delete_loading_animation(chat_id,
                                             loading_animation.message_id)

    def run(self):
        """Starts the Telegram bot polling."""
        logger.info("✅ تم تشغيل البوت ويستعد لاستقبال روابط AliExpress...")
        logger.info(
            f"🔑 مفتاح التطبيق المستخدم: {self.aliexpress_client.app_key[:4]}..."
        )
        logger.info(f"🆔 رقم التتبع: {self.aliexpress_client.tracking_id}")
        logger.info(
            f"📦 إعدادات تفاصيل المنتج: العملة={self.aliexpress_client.target_currency}, اللغة={self.aliexpress_client.target_language}, الدولة={self.aliexpress_client.query_country}"
        )
        logger.info(
            f"📝 الحقول المطلوبة: {self.aliexpress_client.QUERY_FIELDS}")
        logger.info(
            f"🧠 مدة صلاحية التخزين المؤقت: {self.cache_manager.cache_expiry_seconds / (24 * 60 * 60)} يوم"
        )
        offer_names = [o.label for o in OFFER_PARAMS.values()]
        logger.info(
            f"🎯 سيتم إنشاء روابط للعروض التالية: {', '.join(offer_names)}")
        logger.info("🤖 البوت يعمل وينتظر روابط AliExpress...")
        self.application.run_polling()
        logger.info("تم إيقاف البوت.")
