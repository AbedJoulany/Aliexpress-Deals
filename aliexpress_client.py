import logging
import json
import time
import asyncio
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from typing import Union, Dict, List, Tuple, Callable, TypeVar

import requests
import iop  # Assuming iop is installed and available
from cache_manager import CacheManager  # Assuming CacheManager is in cache_manager.py
from aliexpress_errors import (
    AliExpressError, ProductNotFoundError, RateLimitError, NetworkError,
    InvalidResponseError, APIError, classify_api_error)

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.INFO)

T = TypeVar('T')
MAX_ATTEMPTS = 3
INITIAL_BACKOFF_SECONDS = 0.5


class AliExpressClient:
    ALIEXPRESS_API_URL = 'https://api-sg.aliexpress.com/sync'
    QUERY_FIELDS = 'product_main_image_url,target_sale_price,product_title,target_sale_price_currency'
    MAX_ATTEMPTS = MAX_ATTEMPTS
    INITIAL_BACKOFF_SECONDS = INITIAL_BACKOFF_SECONDS

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

    def _retry_sync(self, func: Callable[[], T]) -> T:
        """Retry a blocking call for transient network and rate-limit errors."""
        delay = self.INITIAL_BACKOFF_SECONDS
        last_error: AliExpressError | None = None
        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                return func()
            except (NetworkError, RateLimitError) as exc:
                last_error = exc
                if attempt >= self.MAX_ATTEMPTS:
                    break
                logger.warning(
                    f"Transient AliExpress error (attempt {attempt}/{self.MAX_ATTEMPTS}): {exc}. "
                    f"Retrying in {delay}s")
                time.sleep(delay)
                delay *= 2
        raise last_error or NetworkError("AliExpress request failed")

    def _execute_iop_request(self, request):
        """Execute an IOP request and map transport failures to typed errors."""
        try:
            return self.client.execute(request)
        except (requests.RequestException, TimeoutError, OSError) as e:
            raise NetworkError(str(e)) from e
        except AliExpressError:
            raise
        except Exception as e:
            raise APIError(str(e)) from e

    def _response_body_as_dict(self, response) -> dict:
        if not response or not getattr(response, 'body', None):
            raise InvalidResponseError("Empty AliExpress API response")

        response_data = response.body
        if isinstance(response_data, str):
            try:
                response_data = json.loads(response_data)
            except json.JSONDecodeError as json_err:
                raise InvalidResponseError(
                    f"Failed to decode JSON response: {json_err}") from json_err

        if not isinstance(response_data, dict):
            raise InvalidResponseError("API response is not a JSON object")
        return response_data

    def _raise_if_error_response(self, response_data: dict) -> None:
        if 'error_response' not in response_data:
            return
        error_details = response_data.get('error_response', {}) or {}
        raise classify_api_error(error_details.get('code', 'N/A'),
                                 error_details.get('msg', 'Unknown API error'))

    def _execute_product_detail_request(self, product_id: str):
        request = iop.IopRequest('aliexpress.affiliate.productdetail.get')
        request.add_api_param('fields', self.QUERY_FIELDS)
        request.add_api_param('product_ids', product_id)
        request.add_api_param('target_currency', self.target_currency)
        request.add_api_param('target_language', self.target_language)
        request.add_api_param('tracking_id', self.tracking_id)
        request.add_api_param('country', self.query_country)
        return self._execute_iop_request(request)

    def _parse_product_response(self, response, product_id: str) -> dict:
        try:
            response_data = self._response_body_as_dict(response)
            self._raise_if_error_response(response_data)

            detail_response = response_data.get(
                'aliexpress_affiliate_productdetail_get_response')
            if not detail_response:
                raise InvalidResponseError(
                    f"Missing product detail response key for ID {product_id}")

            resp_result = detail_response.get('resp_result')
            if not resp_result:
                raise InvalidResponseError(
                    f"Missing resp_result for ID {product_id}")

            resp_code = resp_result.get('resp_code')
            if resp_code != 200:
                resp_msg = resp_result.get('resp_msg', 'Unknown response message')
                classified = classify_api_error(resp_code, resp_msg)
                if resp_code in (404, '404') or isinstance(
                        classified, ProductNotFoundError):
                    raise ProductNotFoundError(
                        resp_msg or f"Product {product_id} not found")
                raise classified

            result = resp_result.get('result', {}) or {}
            products = result.get('products', {}).get('product', [])

            if not products:
                raise ProductNotFoundError(
                    f"No products found in API response for ID {product_id}")

            product_data = products[0]
            return {
                'image_url': product_data.get('product_main_image_url'),
                'price': product_data.get('target_sale_price'),
                'currency': product_data.get('target_sale_price_currency',
                                             self.target_currency),
                'title': product_data.get('product_title',
                                          f'Product {product_id}')
            }
        except AliExpressError:
            raise
        except (TypeError, AttributeError, KeyError, IndexError) as e:
            raise InvalidResponseError(
                f"Unexpected product API data for ID {product_id}") from e

    def _fetch_product_details_sync(self, product_id: str) -> dict:
        def _once():
            response = self._execute_product_detail_request(product_id)
            return self._parse_product_response(response, product_id)

        return self._retry_sync(_once)

    async def fetch_product_details(self, product_id: str) -> dict:
        """Fetches product details using aliexpress.affiliate.productdetail.get with async cache."""
        cached_data = await self.cache_manager.product_cache.get(product_id)
        if cached_data:
            logger.debug(f"Cache hit for product ID: {product_id}")
            return cached_data

        logger.info(f"Fetching product details for ID: {product_id}")
        loop = asyncio.get_event_loop()
        product_info = await loop.run_in_executor(
            self.executor, self._fetch_product_details_sync, product_id)

        await self.cache_manager.product_cache.set(product_id, product_info)
        expiry_date = datetime.now() + timedelta(
            seconds=self.cache_manager.cache_expiry_seconds)
        logger.info(
            f"Cached product {product_id} until {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        return product_info

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

        Returns:
            A comma-separated string of prepared URLs.
        """
        return ",".join(uncached_urls)

    def _execute_batch_link_api_call(self, source_values_str: str):
        """
        Executes the blocking AliExpress batch link generation API call.

        Args:
            source_values_str: Comma-separated string of URLs for the API.

        Returns:
            The raw response from the IOP client.
        """
        request = iop.IopRequest('aliexpress.affiliate.link.generate')
        request.add_api_param('promotion_link_type', '0')
        request.add_api_param('source_values', source_values_str)
        request.add_api_param('tracking_id', self.tracking_id)
        return self._execute_iop_request(request)

    def _parse_api_promotion_response(
            self, response_body: Union[str, Dict, None]) -> List[Dict]:
        """
        Parses the nested JSON response from the batch link generation API.

        Returns:
            A list of dictionaries, each containing 'source_value' and 'promotion_link'.
        """
        class _BodyResponse:
            def __init__(self, body):
                self.body = body
                self.code = None
                self.message = None

        response_data = self._response_body_as_dict(
            _BodyResponse(response_body))
        self._raise_if_error_response(response_data)

        generate_response = response_data.get(
            'aliexpress_affiliate_link_generate_response')
        if not generate_response:
            raise InvalidResponseError(
                "Missing aliexpress_affiliate_link_generate_response key")

        resp_result_outer = generate_response.get('resp_result')
        if not resp_result_outer:
            raise InvalidResponseError(
                "Missing resp_result key in batch link response")

        resp_code = resp_result_outer.get('resp_code')
        if resp_code != 200:
            resp_msg = resp_result_outer.get('resp_msg',
                                             'Unknown response message')
            raise classify_api_error(resp_code, resp_msg)

        result = resp_result_outer.get('result', {})
        if not result:
            raise InvalidResponseError(
                "Missing result key in batch link response")

        links_data = result.get('promotion_links',
                                {}).get('promotion_link', [])
        if not links_data or not isinstance(links_data, list):
            logger.warning(
                "No 'promotion_links' found or not a list in batch response.")
            return []

        logger.info(f"Batch API response contains {len(links_data)} links.")
        return [
            link_info for link_info in links_data
            if isinstance(link_info, dict)
        ]

    def _fetch_batch_links_sync(self, source_values_str: str) -> List[Dict]:
        def _once():
            raw_response = self._execute_batch_link_api_call(source_values_str)
            return self._parse_api_promotion_response(
                raw_response.body if raw_response else None)

        return self._retry_sync(_once)

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

        for url in uncached_urls:
            if results_dict.get(url) is None:
                logger.warning(
                    f"No affiliate link returned or processed for requested URL: {url}"
                )

    async def generate_affiliate_links_batch(
            self, target_urls: List[str]) -> Dict[str, Union[str, None]]:
        """
        Generates affiliate links for a list of target URLs using a single API call for uncached URLs.
        Checks cache first, then fetches missing links in a batch.
        Returns a dictionary mapping each original target_url to its affiliate link (or None if failed).
        """
        results_dict, uncached_urls = await self._check_cache_for_links(
            target_urls)

        if not uncached_urls:
            logger.info("All affiliate links retrieved from cache.")
            return results_dict

        logger.debug(
            f"Generating affiliate links for {len(uncached_urls)} uncached URLs: {', '.join(uncached_urls[:3])}...\n"
        )

        source_values_str = self._prepare_api_source_values(uncached_urls)
        loop = asyncio.get_event_loop()
        try:
            api_links_data = await loop.run_in_executor(
                self.executor, self._fetch_batch_links_sync, source_values_str)
        except AliExpressError as e:
            logger.error(f"Batch affiliate link generation failed: {e}")
            api_links_data = []

        await self._update_results_and_cache(results_dict, uncached_urls,
                                             api_links_data)
        return results_dict
