# url_processor.py
import re
import logging
import asyncio
import aiohttp
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs  # Import parse_qs

from cache_manager import CacheManager

logger = logging.getLogger(__name__)


class URLProcessor:
    URL_REGEX = re.compile(
        r'https?://[^\s<>"]+|www\.[^\s<>"]+|\b(?:s\.click\.|a\.)?aliexpress\.(?:com|ru|es|fr|pt|it|pl|nl|co\.kr|co\.jp|com\.br|com\.tr|com\.vn|us|id|th|ar)(?:\.[\w-]+)?/[^\s<>"]*',
        re.IGNORECASE)
    PRODUCT_ID_REGEX = re.compile(r'/item/(\d+)\.html')
    STANDARD_ALIEXPRESS_DOMAIN_REGEX = re.compile(
        r'https?://(?!a\.|s\.click\.)([\w-]+\.)?aliexpress\.(com|ru|es|fr|pt|it|pl|nl|co\.kr|co\.jp|com\.br|com\.tr|com\.vn|us|id\.aliexpress\.com|th\.aliexpress\.com|ar\.aliexpress\.com)(\.([\w-]+))?(/.*)?',
        re.IGNORECASE)
    SHORT_LINK_DOMAIN_REGEX = re.compile(
        r'https?://(?:s\.click\.aliexpress\.com/e/|a\.aliexpress\.com/_)[a-zA-Z0-9_-]+/?',
        re.IGNORECASE)

    def __init__(self, query_country: str, cache_manager: CacheManager):
        self.query_country = query_country
        self.cache_manager = cache_manager

    async def resolve_short_link(self, short_url: str,
                                 session: aiohttp.ClientSession) -> str | None:
        """Follows redirects for a short URL to find the final destination URL."""
        cached_final_url = await self.cache_manager.resolved_url_cache.get(
            short_url)
        if cached_final_url:
            logger.debug(
                f"Cache hit for resolved short link: {short_url} -> {cached_final_url}"
            )
            return cached_final_url

        logger.debug(f"Resolving short link: {short_url}")
        try:
            async with session.get(short_url, allow_redirects=True,
                                   timeout=10) as response:
                if response.status == 200 and response.url:
                    final_url = str(response.url)
                    logger.info(f"Resolved {short_url} to {final_url}")

                    if '.aliexpress.us' in final_url:
                        logger.debug(
                            f"Detected US domain in {final_url}, converting to .com domain"
                        )
                        final_url = final_url.replace('.aliexpress.us',
                                                      '.aliexpress.com')
                        logger.debug(f"Converted URL: {final_url}")

                    if '_randl_shipto=' in final_url:
                        logger.debug(
                            f"Found _randl_shipto parameter in URL, replacing with QUERY_COUNTRY value"
                        )
                        final_url = re.sub(
                            r'_randl_shipto=[^&]+',
                            f'_randl_shipto={self.query_country}', final_url)
                        logger.debug(
                            f"Updated URL with correct country: {final_url}")

                        try:
                            logger.debug(
                                f"Re-fetching URL with updated country parameter: {final_url}"
                            )
                            async with session.get(
                                    final_url, allow_redirects=True,
                                    timeout=10) as country_response:
                                if country_response.status == 200 and country_response.url:
                                    final_url = str(country_response.url)
                                    logger.info(
                                        f"Re-fetched URL with correct country: {final_url}"
                                    )
                        except Exception as e:
                            logger.warning(
                                f"Error re-fetching URL with updated country parameter: {e}"
                            )

                    product_id = self.extract_product_id(final_url)
                    if self.STANDARD_ALIEXPRESS_DOMAIN_REGEX.match(
                            final_url) and product_id:
                        await self.cache_manager.resolved_url_cache.set(
                            short_url, final_url)
                        return final_url
                    else:
                        logger.warning(
                            f"Resolved URL {final_url} doesn't look like a valid AliExpress product page."
                        )
                        return None
                else:
                    logger.error(
                        f"Failed to resolve short link {short_url}. Status: {response.status}"
                    )
                    return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout resolving short link: {short_url}")
            return None
        except aiohttp.ClientError as e:
            logger.error(
                f"HTTP ClientError resolving short link {short_url}: {e}")
            return None
        except Exception as e:
            logger.exception(
                f"Unexpected error resolving short link {short_url}: {e}")
            return None

    def extract_product_id(self, url: str) -> str | None:
        """Extracts the product ID from an AliExpress URL."""
        if '.aliexpress.us' in url:
            url = url.replace('.aliexpress.us', '.aliexpress.com')
            logger.debug(
                f"Converted .us URL to .com format for product ID extraction: {url}"
            )

        # New method: Try to extract from 'productIds' query parameter
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        if 'productIds' in query_params and query_params['productIds']:
            product_id_from_param = query_params['productIds'][0]
            # Validate that the extracted value is purely numeric
            if product_id_from_param.isdigit():
                logger.info(
                    f"Extracted product ID {product_id_from_param} from 'productIds' parameter."
                )
                return product_id_from_param

        # Existing methods: Try the primary regex pattern
        match = self.PRODUCT_ID_REGEX.search(url)
        if match:
            return match.group(1)

        # Existing methods: Try alternative patterns
        alt_patterns = [r'/p/[^/]+/([0-9]+)\.html', r'product/([0-9]+)']

        for pattern in alt_patterns:
            alt_match = re.search(pattern, url)
            if alt_match:
                product_id = alt_match.group(1)
                logger.info(
                    f"Extracted product ID {product_id} using alternative pattern {pattern}"
                )
                return product_id

        logger.warning(f"Could not extract product ID from URL: {url}")
        return None

    def extract_potential_aliexpress_urls(self, text: str) -> list[str]:
        """Finds potential AliExpress URLs (standard and short) in text using regex."""
        return self.URL_REGEX.findall(text)

    def clean_aliexpress_url(self, url: str, product_id: str) -> str | None:
        """Reconstructs a clean base URL (scheme, domain, path) for a given product ID."""
        try:
            parsed_url = urlparse(url)
            path_segment = f'/item/{product_id}.html'
            base_url = urlunparse(
                (parsed_url.scheme
                 or 'https', parsed_url.netloc, path_segment, '', '', ''))
            return base_url
        except ValueError:
            logger.warning(f"Could not parse or reconstruct URL: {url}")
            return None

    def build_url_with_offer_params(self, base_url: str,
                                    params_to_add: dict) -> str:
        """Adds offer parameters to a base URL."""
        if not params_to_add:
            return base_url

        try:
            parsed_url = urlparse(base_url)

            netloc = parsed_url.netloc
            if '.' in netloc and netloc.count('.') > 1:
                parts = netloc.split('.')
                if len(parts) >= 2 and 'aliexpress' in parts[-2]:
                    netloc = f"aliexpress.{parts[-1]}"

            if 'sourceType' in params_to_add and '%26' in params_to_add[
                    'sourceType']:
                new_query_string = '&'.join([
                    f"{k}={v}" for k, v in params_to_add.items()
                    if k != 'channel'
                    and '%26channel=' in params_to_add['sourceType']
                ])
            else:
                new_query_string = urlencode(params_to_add)

            reconstructed_url = urlunparse(
                (parsed_url.scheme, netloc, parsed_url.path, '',
                 new_query_string, ''))
            reconstructed_url = f"https://star.aliexpress.com/share/share.htm?&redirectUrl={reconstructed_url}"
            return reconstructed_url
        except ValueError:
            logger.error(
                f"Error building URL with params for base: {base_url}")
            return base_url
