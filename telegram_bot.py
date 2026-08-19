import logging
import re
import asyncio
from datetime import timedelta

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode, ChatAction

from product_service import ProductService
from url_processor import URLProcessor
from cache_manager import CacheManager
from constants import OFFER_PARAMS
from message_formatter import (
    format_product_message, format_no_offers_message, truncate_telegram_text,
    caption_fits)

logger = logging.getLogger(__name__)


class TelegramBot:

    def __init__(self, token: str, product_service: ProductService,
                 url_processor: URLProcessor, cache_manager: CacheManager):
        self.token = token
        self.product_service = product_service
        self.url_processor = url_processor
        self.cache_manager = cache_manager
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
        text_to_send = truncate_telegram_text(response_text)

        try:
            if product_image and caption_fits(text_to_send):
                await self.application.bot.send_photo(
                    chat_id=chat_id,
                    photo=product_image,
                    caption=text_to_send,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup)
                return

            if product_image and not caption_fits(text_to_send):
                try:
                    await self.application.bot.send_photo(
                        chat_id=chat_id, photo=product_image)
                except Exception as photo_error:
                    logger.warning(
                        f"Failed to send product image for chat {chat_id}: {photo_error}"
                    )
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=text_to_send,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    reply_markup=reply_markup)
                return

            await self.application.bot.send_message(
                chat_id=chat_id,
                text=text_to_send,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=reply_markup)
        except Exception as send_error:
            logger.error(
                f"Failed to send message with keyboard for chat {chat_id}: {send_error}"
            )
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=
                f"⚠️ حدث خطأ أثناء إرسال الرسالة. إليك العروض المتوفرة:\n\n{text_to_send}",
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
            product_info = await self.product_service.get_product(product_id)
            if product_info.get('source') == "AuthError":
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=
                    "⚠️ تعذر الاتصال بخدمة AliExpress حالياً. يرجى المحاولة لاحقاً."
                )
                return

            product_title = product_info.get('title', f"Product {product_id}")
            product_image = product_info.get('image_url')

            generated_links, success_count = (
                await self.product_service.get_affiliate_links(
                    base_url, product_id))

            response_text = format_product_message(product_info,
                                                   generated_links)
            reply_markup = self._create_inline_keyboard()

            if success_count > 0:
                await self._send_product_message(chat_id, response_text,
                                                 product_image, reply_markup)
            else:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=format_no_offers_message(product_title),
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
        client = self.product_service.aliexpress_client
        logger.info("✅ تم تشغيل البوت ويستعد لاستقبال روابط AliExpress...")
        logger.info(f"🔑 مفتاح التطبيق المستخدم: {client.app_key[:4]}...")
        logger.info(f"🆔 رقم التتبع: {client.tracking_id}")
        logger.info(
            f"📦 إعدادات تفاصيل المنتج: العملة={client.target_currency}, اللغة={client.target_language}, الدولة={client.query_country}"
        )
        logger.info(f"📝 الحقول المطلوبة: {client.QUERY_FIELDS}")
        logger.info(
            f"🧠 مدة صلاحية التخزين المؤقت: {self.cache_manager.cache_expiry_seconds / (24 * 60 * 60)} يوم"
        )
        offer_names = [o.label for o in OFFER_PARAMS.values()]
        logger.info(
            f"🎯 سيتم إنشاء روابط للعروض التالية: {', '.join(offer_names)}")
        logger.info("🤖 البوت يعمل وينتظر روابط AliExpress...")
        self.application.run_polling()
        logger.info("تم إيقاف البوت.")
