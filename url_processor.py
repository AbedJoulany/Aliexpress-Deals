# url_processor.py
import re
import logging
import asyncio
import aiohttp
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

from cache_manager import CacheManager
from offers import _wrap_url_with_star_aliexpress

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
_ALIEXPRESS_BASE_DOMAINS = (
    'aliexpress.com',
    'aliexpress.ru',
    'aliexpress.es',
    'aliexpress.fr',
    'aliexpress.pt',
    'aliexpress.it',
    'aliexpress.pl',
    'aliexpress.nl',
    'aliexpress.co.kr',
    'aliexpress.co.jp',
    'aliexpress.com.br',
    'aliexpress.com.tr',
    'aliexpress.com.vn',
    'aliexpress.us',
    'aliexpress.id',
    'aliexpress.th',
    'aliexpress.ar',
)


def is_aliexpress_host(host: str | None) -> bool:
    """Return True if host is an AliExpress domain or subdomain."""
    if not host:
        return False
    normalized = host.lower().rstrip('.')
    for base in _ALIEXPRESS_BASE_DOMAINS:
        if normalized == base or normalized.endswith('.' + base):
            return True
    return False


def force_https(url: str) -> str:
    """Upgrade an http URL to https without otherwise changing it."""
    if url.startswith('http://'):
        return 'https://' + url[7:]
    return url


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
    MAX_REDIRECTS = MAX_REDIRECTS

    def __init__(self, query_country: str, cache_manager: CacheManager):
        self.query_country = query_country
        self.cache_manager = cache_manager

    def _hostname(self, url: str) -> str | None:
        try:
            host = urlparse(url).hostname
        except ValueError:
            return None
        if not host:
            return None
        return host.lower().rstrip('.')

    def _redirect_chain_is_safe(self, response) -> bool:
        """Reject redirect chains that leave AliExpress hosts."""
        hops = list(getattr(response, 'history', ()) or ())
        hop_urls = [str(hop.url) for hop in hops if getattr(hop, 'url', None)]
        hop_urls.append(str(response.url) if response.url else '')
        for hop_url in hop_urls:
            scheme = urlparse(hop_url).scheme.lower()
            if scheme not in ('http', 'https'):
                logger.warning(
                    f"Rejecting redirect hop with unexpected scheme: {hop_url}"
                )
                return False
            if not is_aliexpress_host(self._hostname(hop_url)):
                logger.warning(
                    f"Rejecting redirect hop to non-AliExpress host: {hop_url}"
                )
                return False
        return True

    def _is_safe_product_destination(self, url: str) -> bool:
        if not url:
            return False
        parsed = urlparse(url)
        if parsed.scheme != 'https':
            return False
        if not is_aliexpress_host(parsed.hostname):
            return False
        return True

    def _fetch_following_redirects(self, url: str,
                                   session: aiohttp.ClientSession):
        timeout = aiohttp.ClientTimeout(total=10)
        return session.get(
            url,
            allow_redirects=True,
            max_redirects=self.MAX_REDIRECTS,
            timeout=timeout,
            ssl=True,
        )

    async def resolve_short_link(self, short_url: str,
                                 session: aiohttp.ClientSession) -> str | None:
        """Follows redirects for a short URL to find the final destination URL."""
        cached_final_url = await self.cache_manager.resolved_url_cache.get(
            short_url)
        if cached_final_url:
            cached_final_url = force_https(cached_final_url)
            if self._is_safe_product_destination(cached_final_url):
                logger.debug(
                    f"Cache hit for resolved short link: {short_url} -> {cached_final_url}"
                )
                return cached_final_url
            logger.warning(
                f"Ignoring cached short-link destination that is no longer allowed: {cached_final_url}"
            )

        request_url = force_https(short_url)
        if urlparse(request_url).scheme != 'https':
            logger.warning(
                f"Refusing to resolve short link with non-HTTPS scheme: {short_url}"
            )
            return None
        if not is_aliexpress_host(self._hostname(request_url)):
            logger.warning(
                f"Refusing to resolve non-AliExpress short link host: {short_url}"
            )
            return None

        logger.debug(f"Resolving short link: {short_url}")
        try:
            async with self._fetch_following_redirects(
                    request_url, session) as response:
                if response.status == 200 and response.url:
                    if not self._redirect_chain_is_safe(response):
                        return None

                    final_url = force_https(str(response.url))
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
                            country_url = force_https(final_url)
                            if is_aliexpress_host(self._hostname(country_url)):
                                logger.debug(
                                    f"Re-fetching URL with updated country parameter: {country_url}"
                                )
                                async with self._fetch_following_redirects(
                                        country_url,
                                        session) as country_response:
                                    if (country_response.status == 200
                                            and country_response.url
                                            and self._redirect_chain_is_safe(
                                                country_response)):
                                        final_url = force_https(
                                            str(country_response.url))
                                        logger.info(
                                            f"Re-fetched URL with correct country: {final_url}"
                                        )
                        except Exception as e:
                            logger.warning(
                                f"Error re-fetching URL with updated country parameter: {e}"
                            )

                    final_url = force_https(final_url)
                    product_id = self.extract_product_id(final_url)
                    if (self._is_safe_product_destination(final_url)
                            and self.STANDARD_ALIEXPRESS_DOMAIN_REGEX.match(
                                final_url) and product_id):
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
        except aiohttp.TooManyRedirects:
            logger.error(
                f"Too many redirects resolving short link: {short_url}")
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
            return _wrap_url_with_star_aliexpress(reconstructed_url)
        except ValueError:
            logger.error(
                f"Error building URL with params for base: {base_url}")
            return base_url
