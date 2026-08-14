import unittest
from unittest.mock import AsyncMock, MagicMock

from url_processor import URLProcessor, is_aliexpress_host, force_https


def _make_processor(query_country='US'):
    cache_manager = MagicMock()
    cache_manager.resolved_url_cache.get = AsyncMock(return_value=None)
    cache_manager.resolved_url_cache.set = AsyncMock()
    return URLProcessor(query_country=query_country, cache_manager=cache_manager)


class URLProcessingTests(unittest.TestCase):

    def setUp(self):
        self.processor = _make_processor()

    def test_normal_product_url(self):
        url = 'https://www.aliexpress.com/item/1234567890.html'
        self.assertTrue(self.processor.STANDARD_ALIEXPRESS_DOMAIN_REGEX.match(url))
        self.assertEqual(self.processor.extract_product_id(url), '1234567890')
        self.assertEqual(
            self.processor.clean_aliexpress_url(url, '1234567890'),
            'https://www.aliexpress.com/item/1234567890.html')

    def test_mobile_product_url(self):
        url = 'https://m.aliexpress.com/item/1234567890.html'
        self.assertTrue(self.processor.STANDARD_ALIEXPRESS_DOMAIN_REGEX.match(url))
        self.assertEqual(self.processor.extract_product_id(url), '1234567890')

    def test_country_specific_product_url(self):
        urls = [
            'https://ko.aliexpress.com/item/100500123.html',
            'https://pt.aliexpress.com/item/100500123.html',
            'https://aliexpress.ru/item/100500123.html',
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(
                    self.processor.STANDARD_ALIEXPRESS_DOMAIN_REGEX.match(url),
                    url)
                self.assertEqual(self.processor.extract_product_id(url),
                                 '100500123')

    def test_short_url(self):
        url = 'https://s.click.aliexpress.com/e/_abcDEF123'
        self.assertTrue(self.processor.SHORT_LINK_DOMAIN_REGEX.match(url))
        self.assertIsNone(self.processor.extract_product_id(url))
        found = self.processor.extract_potential_aliexpress_urls(
            f'check this {url} please')
        self.assertTrue(any(url in item for item in found))

    def test_invalid_url(self):
        self.assertIsNone(self.processor.extract_product_id('not-a-url'))
        self.assertIsNone(
            self.processor.STANDARD_ALIEXPRESS_DOMAIN_REGEX.match(
                'https://example.com/foo'))
        self.assertFalse(is_aliexpress_host('example.com'))
        self.assertFalse(is_aliexpress_host('evilaliexpress.com'))

    def test_non_product_url(self):
        url = 'https://www.aliexpress.com/wholesale?SearchText=phone'
        self.assertTrue(self.processor.STANDARD_ALIEXPRESS_DOMAIN_REGEX.match(url))
        self.assertIsNone(self.processor.extract_product_id(url))


class RedirectValidationTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.processor = _make_processor()

    async def test_accepts_aliexpress_https_destination(self):
        final = 'https://www.aliexpress.com/item/1234567890.html'
        session = MagicMock()
        session.get.return_value = _async_response(final)
        result = await self.processor.resolve_short_link(
            'https://s.click.aliexpress.com/e/_abc123', session)
        self.assertEqual(result, final)

    async def test_rejects_external_destination(self):
        session = MagicMock()
        session.get.return_value = _async_response(
            'https://evil.example/phish')
        result = await self.processor.resolve_short_link(
            'https://s.click.aliexpress.com/e/_abc123', session)
        self.assertIsNone(result)

    async def test_rejects_external_redirect_hop(self):
        session = MagicMock()
        session.get.return_value = _async_response(
            'https://www.aliexpress.com/item/123.html',
            history_urls=['https://evil.example/hop'])
        result = await self.processor.resolve_short_link(
            'https://s.click.aliexpress.com/e/_abc123', session)
        self.assertIsNone(result)

    async def test_upgrades_http_to_https(self):
        self.assertEqual(
            force_https('http://www.aliexpress.com/item/1.html'),
            'https://www.aliexpress.com/item/1.html')
        session = MagicMock()
        session.get.return_value = _async_response(
            'http://www.aliexpress.com/item/1234567890.html')
        result = await self.processor.resolve_short_link(
            'http://s.click.aliexpress.com/e/_abc123', session)
        self.assertEqual(result,
                         'https://www.aliexpress.com/item/1234567890.html')
        called_url = session.get.call_args.args[0]
        self.assertTrue(called_url.startswith('https://'))
        self.assertEqual(session.get.call_args.kwargs.get('max_redirects'), 5)


class _AsyncResponse:

    def __init__(self, url, status=200, history_urls=None):
        self.url = url
        self.status = status
        self.history = [
            MagicMock(url=hop) for hop in (history_urls or [])
        ]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _async_response(url, status=200, history_urls=None):
    return _AsyncResponse(url, status=status, history_urls=history_urls)


if __name__ == '__main__':
    unittest.main()
