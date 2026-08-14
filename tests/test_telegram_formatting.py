import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from aliexpress_client import AliExpressClient
from telegram_bot import (
    TELEGRAM_CAPTION_MAX_LENGTH, TelegramBot, _safe_html_href)


def _make_bot():
    with patch('telegram_bot.Application') as mock_app:
        built = MagicMock()
        mock_app.builder.return_value.token.return_value.build.return_value = built
        bot = TelegramBot(
            token='123:ABC',
            aliexpress_client=MagicMock(),
            url_processor=MagicMock(),
            cache_manager=MagicMock(),
            executor=MagicMock())
        bot.application = built
        return bot


class TelegramFormattingTests(unittest.TestCase):

    def setUp(self):
        self.bot = _make_bot()

    def _format(self, title, price='9.99', currency='USD', link=None):
        product_info = {
            'title': title,
            'price': price,
            'currency': currency,
            'source': 'API',
        }
        generated_links = {}
        if link is not None:
            from constants import OFFER_ORDER
            for key in OFFER_ORDER:
                generated_links[key] = link
        return self.bot._format_response_message(product_info, generated_links)

    def test_normal_product_title(self):
        text = self._format('Wireless earbuds')
        self.assertIn('Wireless earbuds', text)
        self.assertIn('<b>', text)

    def test_title_containing_lt(self):
        text = self._format('Size < medium')
        self.assertIn('Size &lt; medium', text)
        self.assertNotIn('Size < medium', text)

    def test_title_containing_gt(self):
        text = self._format('Size > medium')
        self.assertIn('Size &gt; medium', text)
        self.assertNotIn('Size > medium', text)

    def test_title_containing_amp(self):
        text = self._format('Black & White')
        self.assertIn('Black &amp; White', text)
        self.assertNotIn('Black & White', text)

    def test_arabic_text(self):
        text = self._format('سماعة لاسلكية')
        self.assertIn('سماعة لاسلكية', text)
        self.assertIn('السعر بعد الخصم', text)
        self.assertIn('العروض المتاحة', text)

    def test_long_product_title(self):
        title = 'A' * 400
        text = self._format(title)
        self.assertIn('A' * 250, text)
        self.assertNotIn('A' * 251, text)

    def test_href_is_html_escaped(self):
        link = 'https://s.click.aliexpress.com/e/_x?foo=1&bar=2'
        text = self._format('Title', link=link)
        self.assertIn('href="https://s.click.aliexpress.com/e/_x?foo=1&amp;bar=2"',
                      text)
        self.assertNotIn('href="https://s.click.aliexpress.com/e/_x?foo=1&bar=2"',
                         text)

    def test_javascript_url_is_rejected(self):
        self.assertIsNone(_safe_html_href('javascript:alert(1)'))
        text = self._format('Title', link='javascript:alert(1)')
        self.assertNotIn('javascript:', text)
        self.assertIn('فشل في الإنشاء', text)


class TelegramCaptionLengthTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.bot = _make_bot()
        self.bot.application.bot.send_photo = AsyncMock()
        self.bot.application.bot.send_message = AsyncMock()

    async def test_long_caption_sends_photo_then_text(self):
        long_text = 'x' * (TELEGRAM_CAPTION_MAX_LENGTH + 50)
        markup = MagicMock()
        await self.bot._send_product_message(
            chat_id=1,
            response_text=long_text,
            product_image='https://ae01.alicdn.com/img.jpg',
            reply_markup=markup)
        self.bot.application.bot.send_photo.assert_awaited()
        photo_kwargs = self.bot.application.bot.send_photo.call_args.kwargs
        self.assertNotIn('caption', photo_kwargs)
        self.bot.application.bot.send_message.assert_awaited()
        self.assertEqual(
            self.bot.application.bot.send_message.call_args.kwargs['text'],
            long_text)

    async def test_short_caption_sent_with_photo(self):
        short_text = 'short caption'
        markup = MagicMock()
        await self.bot._send_product_message(
            chat_id=1,
            response_text=short_text,
            product_image='https://ae01.alicdn.com/img.jpg',
            reply_markup=markup)
        self.bot.application.bot.send_photo.assert_awaited()
        self.assertEqual(
            self.bot.application.bot.send_photo.call_args.kwargs['caption'],
            short_text)
        self.bot.application.bot.send_message.assert_not_awaited()


class MalformedProductFallbackTests(unittest.IsolatedAsyncioTestCase):

    async def test_malformed_product_api_data_uses_scraping_fallback(self):
        bot = _make_bot()
        with patch('aliexpress_client.iop.IopClient'):
            parser = AliExpressClient(
                app_key='key',
                app_secret='secret',
                tracking_id='track',
                target_currency='USD',
                target_language='en',
                query_country='US',
                executor=MagicMock(),
                cache_manager=MagicMock())

        malformed_response = MagicMock()
        malformed_response.body = {
            'aliexpress_affiliate_productdetail_get_response': {
                'resp_result': {
                    'resp_code': 200,
                    'result': {
                        'products': None
                    }
                }
            }
        }

        async def fetch_malformed(product_id):
            return parser._parse_product_response(malformed_response,
                                                  product_id)

        bot.aliexpress_client.fetch_product_details = fetch_malformed
        bot.executor = None

        with patch('telegram_bot.get_product_details_by_id',
                   return_value=('Scraped Title',
                                 'https://example.com/img.jpg')) as scrape:
            result = await bot._fetch_product_info('123')

        scrape.assert_called_once_with('123')
        self.assertEqual(result['source'], 'Scraped')
        self.assertEqual(result['title'], 'Scraped Title')


if __name__ == '__main__':
    unittest.main()
