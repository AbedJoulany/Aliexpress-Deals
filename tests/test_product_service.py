import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from product_service import ProductService
from constants import OFFER_ORDER


class ProductServiceAffiliateMappingTests(unittest.IsolatedAsyncioTestCase):

    async def test_maps_batch_links_back_to_offer_keys(self):
        client = MagicMock()
        service = ProductService(client, executor=None)
        target_map = {}
        all_urls = []
        for key in OFFER_ORDER:
            url = f'https://example.com/{key}'
            target_map[key] = [url]
            all_urls.append(url)

        service._generate_offer_urls = MagicMock(
            return_value=(target_map, all_urls))
        links = {all_urls[0]: 'https://s.click.aliexpress.com/e/ok'}
        client.generate_affiliate_links_batch = AsyncMock(return_value=links)

        generated, success_count = await service.get_affiliate_links(
            'https://www.aliexpress.com/item/1.html', '1')

        self.assertEqual(success_count, 1)
        self.assertEqual(generated[OFFER_ORDER[0]],
                         'https://s.click.aliexpress.com/e/ok')
        for key in OFFER_ORDER[1:]:
            self.assertIsNone(generated[key])


if __name__ == '__main__':
    unittest.main()
