import unittest
from unittest.mock import MagicMock, patch

from aliexpress_client import AliExpressClient
from aliexpress_errors import (
    ProductNotFoundError, AuthenticationError, RateLimitError, NetworkError,
    InvalidResponseError, APIError, classify_api_error)


def _product_success_body(title='Test Product', price='9.99', currency='USD'):
    return {
        'aliexpress_affiliate_productdetail_get_response': {
            'resp_result': {
                'resp_code': 200,
                'result': {
                    'products': {
                        'product': [{
                            'product_main_image_url':
                            'https://ae01.alicdn.com/img.jpg',
                            'target_sale_price': price,
                            'target_sale_price_currency': currency,
                            'product_title': title,
                        }]
                    }
                }
            }
        }
    }


class FakeIopResponse:

    def __init__(self, body, code=None, message=None):
        self.body = body
        self.code = code
        self.message = message


class AliExpressResponseHandlingTests(unittest.TestCase):

    def setUp(self):
        with patch('aliexpress_client.iop.IopClient'):
            self.client = AliExpressClient(
                app_key='key',
                app_secret='secret',
                tracking_id='track',
                target_currency='USD',
                target_language='en',
                query_country='US',
                executor=MagicMock(),
                cache_manager=MagicMock())

    def test_successful_response(self):
        response = FakeIopResponse(_product_success_body())
        product = self.client._parse_product_response(response, '123')
        self.assertEqual(product['title'], 'Test Product')
        self.assertEqual(product['price'], '9.99')
        self.assertEqual(product['currency'], 'USD')
        self.assertEqual(product['image_url'],
                         'https://ae01.alicdn.com/img.jpg')

    def test_product_not_found(self):
        body = {
            'aliexpress_affiliate_productdetail_get_response': {
                'resp_result': {
                    'resp_code': 200,
                    'result': {
                        'products': {
                            'product': []
                        }
                    }
                }
            }
        }
        with self.assertRaises(ProductNotFoundError):
            self.client._parse_product_response(FakeIopResponse(body), '123')

    def test_api_error(self):
        body = {
            'error_response': {
                'code': '15',
                'msg': 'Remote service error'
            }
        }
        with self.assertRaises(APIError):
            self.client._parse_product_response(FakeIopResponse(body), '123')

    def test_authentication_failure(self):
        body = {
            'error_response': {
                'code': '27',
                'msg': 'Invalid signature'
            }
        }
        with self.assertRaises(AuthenticationError):
            self.client._parse_product_response(FakeIopResponse(body), '123')

    def test_rate_limit(self):
        body = {
            'error_response': {
                'code': '7',
                'msg': 'AppCallLimited'
            }
        }
        with self.assertRaises(RateLimitError):
            self.client._parse_product_response(FakeIopResponse(body), '123')

    def test_invalid_response(self):
        with self.assertRaises(InvalidResponseError):
            self.client._parse_product_response(FakeIopResponse(None), '123')
        with self.assertRaises(InvalidResponseError):
            self.client._parse_product_response(
                FakeIopResponse('{"not": "valid json"'), '123')
        with self.assertRaises(InvalidResponseError):
            self.client._parse_product_response(FakeIopResponse({}), '123')

    def test_classify_api_error_categories(self):
        self.assertIsInstance(
            classify_api_error('27', 'Invalid signature'),
            AuthenticationError)
        self.assertIsInstance(
            classify_api_error('7', 'rate limit exceeded'), RateLimitError)
        self.assertIsInstance(
            classify_api_error('500', 'Service Unavailable'), NetworkError)
        self.assertIsInstance(
            classify_api_error('404', 'product not found'),
            ProductNotFoundError)
        self.assertIsInstance(classify_api_error('15', 'boom'), APIError)

    @patch('aliexpress_client.time.sleep')
    def test_retries_transient_errors_then_succeeds(self, mock_sleep):
        calls = {'n': 0}

        def flaky():
            calls['n'] += 1
            if calls['n'] < 3:
                raise NetworkError('temporary')
            return {'title': 'ok'}

        result = self.client._retry_sync(flaky)
        self.assertEqual(result['title'], 'ok')
        self.assertEqual(calls['n'], 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('aliexpress_client.time.sleep')
    def test_does_not_retry_authentication_errors(self, mock_sleep):
        calls = {'n': 0}

        def fail_auth():
            calls['n'] += 1
            raise AuthenticationError('bad key')

        with self.assertRaises(AuthenticationError):
            self.client._retry_sync(fail_auth)
        self.assertEqual(calls['n'], 1)
        mock_sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
