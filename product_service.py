import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from aliexpress_client import AliExpressClient
from aliexpress_errors import (
    AliExpressError, ProductNotFoundError, AuthenticationError,
    RateLimitError, NetworkError, InvalidResponseError, APIError)
from aliexpress_utils import get_product_details_by_id
from constants import OFFER_PARAMS, OFFER_ORDER

logger = logging.getLogger(__name__)


class ProductService:
    """Looks up product details and affiliate offer links."""

    def __init__(self, aliexpress_client: AliExpressClient,
                 executor: ThreadPoolExecutor | None):
        self.aliexpress_client = aliexpress_client
        self.executor = executor

    async def get_product(self, product_id: str) -> dict:
        """Fetches product details from API, with scraping fallback."""
        try:
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
        except AuthenticationError as e:
            logger.error(
                f"AliExpress authentication/configuration failure for product ID {product_id}: {e}"
            )
            return {'source': "AuthError", 'title': f"Product {product_id}"}
        except ProductNotFoundError as e:
            logger.warning(
                f"Product not found via API for product ID {product_id}: {e}"
            )
        except RateLimitError as e:
            logger.warning(
                f"AliExpress rate limited for product ID {product_id}: {e}. Attempting scraping fallback."
            )
        except NetworkError as e:
            logger.warning(
                f"AliExpress network error for product ID {product_id}: {e}. Attempting scraping fallback."
            )
        except InvalidResponseError as e:
            logger.warning(
                f"Invalid AliExpress API response for product ID {product_id}: {e}. Attempting scraping fallback."
            )
        except APIError as e:
            logger.warning(
                f"AliExpress API error for product ID {product_id}: {e}. Attempting scraping fallback."
            )
        except AliExpressError as e:
            logger.warning(
                f"AliExpress error for product ID {product_id}: {e}. Attempting scraping fallback."
            )

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

        return target_urls_map, all_urls_to_fetch

    async def get_affiliate_links(self, base_url: str,
                                  product_id: str) -> tuple[dict, int]:
        """Generates affiliate links and maps them back to offer keys."""
        target_urls_map, all_urls_to_fetch = self._generate_offer_urls(
            base_url, product_id)

        logger.debug(
            f"DEBUG: all_urls_to_fetch for product {product_id}: {all_urls_to_fetch}"
        )
        logger.info(
            f"Requesting batch affiliate links for {len(all_urls_to_fetch)} URLs."
        )
        all_links_dict = await self.aliexpress_client.generate_affiliate_links_batch(
            all_urls_to_fetch)

        logger.debug(
            f"DEBUG: all_links_dict received for product {product_id}: {all_links_dict}"
        )

        generated_links = {}
        success_count = 0
        for offer_key in OFFER_ORDER:
            logger.debug(
                f"DEBUG: Processing offer_key: {offer_key} for product {product_id}"
            )
            urls_for_offer = target_urls_map.get(offer_key, [])
            logger.debug(
                f"DEBUG: URLs for offer '{offer_key}' (WRAPPED): {urls_for_offer}"
            )

            found_link_for_offer = False
            for url in urls_for_offer:
                logger.debug(
                    f"DEBUG: Checking URL '{url}' in all_links_dict for offer '{offer_key}'"
                )
                link = all_links_dict.get(url)
                if link:
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
        return generated_links, success_count
