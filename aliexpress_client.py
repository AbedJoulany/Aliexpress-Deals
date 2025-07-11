import logging
import json
import asyncio
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from typing import Union, Dict, List, Tuple

import iop  # Assuming iop is installed and available
from cache_manager import CacheManager  # Assuming CacheManager is in cache_manager.py

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.INFO)


class AliExpressClient:
    ALIEXPRESS_API_URL = 'https://api-sg.aliexpress.com/sync'
    QUERY_FIELDS = 'product_main_image_url,target_sale_price,product_title,target_sale_price_currency'

    def __init__(self, app_key: str, app_secret: str, tracking_id: str,
                 target_currency: str, target_language: str,
                 query_country: str, executor: ThreadPoolExecutor,
                 cache_manager: CacheManager):
        self.app_key = app_key
        self.app_secret = app_secret
        self.tracking_id = tracking_id
        self.target_currency = target_currency
        self.target_language = target_language
        self.query_country = query_country
        self.executor = executor
        self.cache_manager = cache_manager

        try:
            self.client = iop.IopClient(self.ALIEXPRESS_API_URL, self.app_key,
                                        self.app_secret)
            logger.info("AliExpress API client initialized.")
        except Exception as e:
            logger.exception(f"Error initializing AliExpress API client: {e}")
            raise

    async def fetch_product_details(self, product_id: str) -> dict | None:
        """Fetches product details using aliexpress.affiliate.productdetail.get with async cache."""
        cached_data = await self.cache_manager.product_cache.get(product_id)
        if cached_data:
            logger.debug(f"Cache hit for product ID: {product_id}")
            return cached_data

        logger.info(f"Fetching product details for ID: {product_id}")

        def _execute_api_call():
            """Execute blocking API call in a thread pool."""
            try:
                request = iop.IopRequest(
                    'aliexpress.affiliate.productdetail.get')
                request.add_api_param('fields', self.QUERY_FIELDS)
                request.add_api_param('product_ids', product_id)
                request.add_api_param('target_currency', self.target_currency)
                request.add_api_param('target_language', self.target_language)
                request.add_api_param('tracking_id', self.tracking_id)
                request.add_api_param('country', self.query_country)
                return self.client.execute(request)
            except Exception as e:
                logger.error(
                    f"Error in API call thread for product {product_id}: {e}")
                return None

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(self.executor, _execute_api_call)

        if not response or not response.body:
            logger.error(
                f"Product detail API call failed or returned empty body for ID: {product_id}"
            )
            return None

        try:
            response_data = response.body
            if isinstance(response_data, str):
                try:
                    response_data = json.loads(response_data)
                except json.JSONDecodeError as json_err:
                    logger.error(
                        f"Failed to decode JSON response for product {product_id}: {json_err}. Response: {response_data[:500]}"
                    )
                    return None

            if 'error_response' in response_data:
                error_details = response_data.get('error_response', {})
                error_msg = error_details.get('msg', 'Unknown API error')
                error_code = error_details.get('code', 'N/A')
                logger.error(
                    f"API Error for Product ID {product_id}: Code={error_code}, Msg={error_msg}"
                )
                return None

            detail_response = response_data.get(
                'aliexpress_affiliate_productdetail_get_response')
            if not detail_response:
                logger.error(
                    f"Missing 'aliexpress_affiliate_productdetail_get_response' key for ID {product_id}. Response: {response_data}"
                )
                return None

            resp_result = detail_response.get('resp_result')
            if not resp_result:
                logger.error(
                    f"Missing 'resp_result' key for ID {product_id}. Response: {detail_response}"
                )
                return None

            resp_code = resp_result.get('resp_code')
            if resp_code != 200:
                resp_msg = resp_result.get('resp_msg',
                                           'Unknown response message')
                logger.error(
                    f"API response code not 200 for ID {product_id}. Code: {resp_code}, Msg: {resp_msg}"
                )
                return None

            result = resp_result.get('result', {})
            products = result.get('products', {}).get('product', [])

            if not products:
                logger.warning(
                    f"No products found in API response for ID {product_id}")
                return None

            product_data = products[0]

            product_info = {
                'image_url':
                product_data.get('product_main_image_url'),
                'price':
                product_data.get('target_sale_price'),
                'currency':
                product_data.get('target_sale_price_currency',
                                 self.target_currency),
                'title':
                product_data.get('product_title', f'Product {product_id}')
            }

            await self.cache_manager.product_cache.set(product_id,
                                                       product_info)
            expiry_date = datetime.now() + timedelta(
                seconds=self.cache_manager.cache_expiry_seconds)
            logger.info(
                f"Cached product {product_id} until {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            return product_info

        except Exception as e:
            logger.exception(
                f"Error parsing product details response for ID {product_id}: {e}"
            )
            return None

    # --- New Helper Methods for generate_affiliate_links_batch ---

    async def _check_cache_for_links(
        self, target_urls: List[str]
    ) -> Tuple[Dict[str, Union[str, None]], List[str]]:
        """
        Checks the cache for existing affiliate links.

        Returns:
            A tuple containing:
            - results_dict: A dictionary pre-filled with cached links.
            - uncached_urls: A list of URLs not found in the cache.
        """
        results_dict: Dict[str, Union[str, None]] = {}
        uncached_urls: List[str] = []

        for url in target_urls:
            #full_affiliate_link_as_key = f"https://star.aliexpress.com/share/share.htm?&redirectUrl={url}"
            cached_link = await self.cache_manager.link_cache.get(url)
            if cached_link:
                logger.info(f"Cache hit for affiliate link: {url}")
                results_dict[url] = cached_link
            else:
                logger.debug(f"Cache miss for affiliate link: {url}")
                results_dict[url] = None  # Initialize as None
                uncached_urls.append(url)
        return results_dict, uncached_urls

    def _prepare_api_source_values(self, uncached_urls: List[str]) -> str:
        """
        Prepares the source_values string for the AliExpress batch link API.
        Adds the required 'star.aliexpress.com/share' prefix if missing.

        Returns:
            A comma-separated string of prepared URLs.
        """
        prefixed_urls = []
        for url in uncached_urls:
            """
            if "star.aliexpress.com/share/share.htm" not in url:
                prefixed_urls.append(
                    f"https://star.aliexpress.com/share/share.htm?&redirectUrl={url}"
                )
            else:
                prefixed_urls.append(url)
            """
            prefixed_urls.append(url)
        return ",".join(prefixed_urls)

    def _execute_batch_link_api_call(self, source_values_str: str):
        """
        Executes the blocking AliExpress batch link generation API call.

        Args:
            source_values_str: Comma-separated string of URLs for the API.

        Returns:
            The raw response from the IOP client, or None if an error occurred.
        """
        try:
            request = iop.IopRequest('aliexpress.affiliate.link.generate')
            request.add_api_param('promotion_link_type', '0')
            request.add_api_param('source_values', source_values_str)
            request.add_api_param('tracking_id', self.tracking_id)
            return self.client.execute(request)
        except Exception as e:
            logger.error(f"Error in batch link API call thread for URLs: {e}",
                         exc_info=True)
            return None

    def _parse_api_promotion_response(
            self, response_body: Union[str, Dict, None]) -> List[Dict]:
        """
        Parses the nested JSON response from the batch link generation API.

        Args:
            response_body: The raw response body (can be string or dict).

        Returns:
            A list of dictionaries, each containing 'source_value' and 'promotion_link',
            or an empty list if parsing fails or no links are found.
        """
        if not response_body:
            logger.error("Empty response body for batch link generation.")
            return []

        response_data = response_body
        if isinstance(response_data, str):
            try:
                response_data = json.loads(response_data)
            except json.JSONDecodeError as json_err:
                logger.error(
                    f"Failed to decode JSON response for batch link generation: {json_err}. Response: {response_data[:500]}"
                )
                return []

        if 'error_response' in response_data:
            error_details = response_data.get('error_response', {})
            error_msg = error_details.get('msg', 'Unknown API error')
            error_code = error_details.get('code', 'N/A')
            logger.error(
                f"API Error for Batch Link Generation: Code={error_code}, Msg={error_msg}"
            )
            return []

        generate_response = response_data.get(
            'aliexpress_affiliate_link_generate_response')
        if not generate_response:
            logger.error(
                f"Missing 'aliexpress_affiliate_link_generate_response' key in batch response. Response: {response_data}"
            )
            return []

        resp_result_outer = generate_response.get('resp_result')
        if not resp_result_outer:
            logger.error(
                f"Missing 'resp_result' key in batch response. Response: {generate_response}"
            )
            return []

        resp_code = resp_result_outer.get('resp_code')
        if resp_code != 200:
            resp_msg = resp_result_outer.get('resp_msg',
                                             'Unknown response message')
            logger.error(
                f"API response code not 200 for batch link generation. Code: {resp_code}, Msg: {resp_msg}"
            )
            return []

        result = resp_result_outer.get('result', {})
        if not result:
            logger.error(
                f"Missing 'result' key in batch link response. Response: {resp_result_outer}"
            )
            return []

        links_data = result.get('promotion_links',
                                {}).get('promotion_link', [])
        if not links_data or not isinstance(links_data, list):
            logger.warning(
                f"No 'promotion_links' found or not a list in batch response. Response: {result}"
            )
            return []

        logger.info(f"Batch API response contains {len(links_data)} links.")

        # Filter out non-dict items for robustness
        return [
            link_info for link_info in links_data
            if isinstance(link_info, dict)
        ]

    async def _update_results_and_cache(self, results_dict: Dict[str,
                                                                 Union[str,
                                                                       None]],
                                        uncached_urls: List[str],
                                        api_links_data: List[Dict]) -> None:
        """
        Updates the results dictionary with newly fetched links and caches them.
        Logs warnings for any URLs that were requested but not returned by the API.
        """
        expiry_date = datetime.now() + timedelta(
            seconds=self.cache_manager.cache_expiry_seconds)
        logger.info(
            f"Processing {len(api_links_data)} links from batch API response.")

        for link_info in api_links_data:
            source_url = link_info.get('source_value')
            promo_link = link_info.get('promotion_link')

            if source_url and promo_link:
                # Only update if the source_url was originally requested and uncached
                if source_url in results_dict:
                    results_dict[source_url] = promo_link
                    await self.cache_manager.link_cache.set(
                        source_url, promo_link)
                    logger.info(
                        f"Cached affiliate link for {source_url} until {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                else:
                    logger.warning(
                        f"Received link for unexpected source_value in batch response: {source_url}. Skipping cache/update."
                    )
            else:
                logger.warning(
                    f"Incomplete promotion link data item in batch response: {link_info}"
                )


# Log any URLs that were in uncached_urls but still don't have an affiliate link
        for url in uncached_urls:
            if results_dict.get(url) is None:
                logger.warning(
                    f"No affiliate link returned or processed for requested URL: {url}"
                )

    # --- Main generate_affiliate_links_batch Function ---

    async def generate_affiliate_links_batch(
            self, target_urls: List[str]) -> Dict[str, Union[str, None]]:
        """
        Generates affiliate links for a list of target URLs using a single API call for uncached URLs.
        Checks cache first, then fetches missing links in a batch.
        Returns a dictionary mapping each original target_url to its affiliate link (or None if failed).
        """
        # 1. Check cache for existing links
        results_dict, uncached_urls = await self._check_cache_for_links(
            target_urls)

        if not uncached_urls:
            logger.info("All affiliate links retrieved from cache.")
            return results_dict

        logger.debug(
            f"Generating affiliate links for {len(uncached_urls)} uncached URLs: {', '.join(uncached_urls[:3])}...\n"
        )

        # 2. Prepare URLs for API call
        source_values_str = self._prepare_api_source_values(uncached_urls)

        # 3. Execute the batch API call in a thread pool
        loop = asyncio.get_event_loop()
        raw_response = await loop.run_in_executor(
            self.executor, self._execute_batch_link_api_call,
            source_values_str)

        # 4. Parse the API response
        api_links_data = self._parse_api_promotion_response(
            raw_response.body if raw_response else None)

        # 5. Update results_dict and cache new links
        await self._update_results_and_cache(results_dict, uncached_urls,
                                             api_links_data)

        return results_dict
