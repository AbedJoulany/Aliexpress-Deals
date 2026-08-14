"""Lightweight AliExpress API error types for retry and fallback decisions."""


class AliExpressError(Exception):
    """Base error for AliExpress API operations."""
    retryable = False


class ProductNotFoundError(AliExpressError):
    """Product does not exist or the API returned no product data."""


class AuthenticationError(AliExpressError):
    """Invalid credentials or application configuration."""


class RateLimitError(AliExpressError):
    """API rate limit exceeded."""
    retryable = True


class NetworkError(AliExpressError):
    """Temporary network or server failure."""
    retryable = True


class InvalidResponseError(AliExpressError):
    """Unexpected or unparseable API response."""


class APIError(AliExpressError):
    """General/permanent AliExpress API failure."""


def classify_api_error(error_code=None, error_msg=None) -> AliExpressError:
    """Map AliExpress/IOP error code and message to a specific exception."""
    code = '' if error_code is None else str(error_code).strip()
    msg = '' if error_msg is None else str(error_msg).strip()
    combined = f"{code} {msg}".lower()
    detail = msg or code or 'AliExpress API error'

    not_found_markers = ('not found', 'does not exist', 'product not exist')
    auth_markers = (
        'unauthorized', 'forbidden', 'invalid signature', 'sign-check',
        'invalid app', 'illegalaccess', 'invalidaccesstoken', 'app key',
        'appkey', 'access denied', 'authentication', 'invalid credentials',
    )
    rate_markers = (
        'rate limit', 'too many', 'throttle', 'frequency', 'calllimited',
        'appcalllimited', 'call limit', 'limit exceeded', '429',
    )
    network_markers = (
        'timeout', 'timed out', 'temporarily', 'service unavailable',
        'internal error', 'system error', 'isp.', 'try again', '502', '503',
        '504',
    )

    if any(marker in combined for marker in not_found_markers):
        return ProductNotFoundError(detail)
    if any(marker in combined for marker in auth_markers):
        return AuthenticationError(detail)
    if any(marker in combined for marker in rate_markers):
        return RateLimitError(detail)
    if any(marker in combined for marker in network_markers):
        return NetworkError(detail)
    return APIError(detail)
