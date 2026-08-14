import unittest
from urllib.parse import quote, urlparse, parse_qs

from offers import StaticOffer, _wrap_url_with_star_aliexpress


class AffiliateUrlEncodingTests(unittest.TestCase):

    def test_normal_redirect_url(self):
        target = 'https://www.aliexpress.com/item/1234567890.html'
        wrapped = _wrap_url_with_star_aliexpress(target)
        parsed = urlparse(wrapped)
        self.assertEqual(parsed.scheme, 'https')
        self.assertEqual(parsed.netloc, 'star.aliexpress.com')
        redirect = parse_qs(parsed.query)['redirectUrl'][0]
        self.assertEqual(redirect, target)
        self.assertIn(quote(target, safe=''), wrapped)

    def test_redirect_url_containing_query_parameters(self):
        target = (
            'https://www.aliexpress.com/item/1234567890.html'
            '?sourceType=562&channel=sd&afSmartRedirect=y')
        wrapped = _wrap_url_with_star_aliexpress(target)
        after_param = wrapped.split('redirectUrl=', 1)[1]
        self.assertNotIn('&channel=', after_param)
        self.assertNotIn('?sourceType=', after_param)
        redirect = parse_qs(urlparse(wrapped).query)['redirectUrl'][0]
        self.assertEqual(redirect, target)

    def test_static_offer_encodes_nested_url(self):
        offer = StaticOffer('super', 'Super', {
            'sourceType': '562',
            'channel': 'sd',
            'afSmartRedirect': 'y'
        })
        urls = offer.build_urls(
            'https://www.aliexpress.com/item/123.html', '123')
        self.assertEqual(len(urls), 1)
        after_param = urls[0].split('redirectUrl=', 1)[1]
        self.assertNotIn('&channel=', after_param)
        redirect = parse_qs(urlparse(urls[0]).query)['redirectUrl'][0]
        self.assertIn('sourceType=562', redirect)
        self.assertIn('channel=sd', redirect)


if __name__ == '__main__':
    unittest.main()
