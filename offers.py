# offers.py
from abc import ABC, abstractmethod
from urllib.parse import urlencode


def _wrap_url_with_star_aliexpress(url: str) -> str:
    """Wraps a URL with the star.aliexpress.com affiliate sharing prefix."""
    return f"https://star.aliexpress.com/share/share.htm?&redirectUrl={url}"


class OfferStrategy(ABC):

    def __init__(self, offer_key: str, label: str):
        self.offer_key = offer_key
        self.label = label

    @abstractmethod
    def build_urls(self, base_url: str, product_id: str) -> list[str]:
        """
        Builds a list containing a single raw URL for the specific offer.
        This URL should be the 'redirectUrl' part, without the 'star.aliexpress.com/share' prefix.
        The URLProcessor will add the 'star.aliexpress.com/share' prefix.
        """
        pass


class CoinOfferProductView(OfferStrategy):
    """عرض العملات - عرض المنتج"""

    def __init__(self):
        super().__init__("coin_product_view", "🪙 عرض العملات (صفحة المنتج)")

    def build_urls(self, base_url: str, product_id: str) -> list[str]:
        raw_url = f"{base_url}?sourceType=620&channel=coin"
        return [_wrap_url_with_star_aliexpress(raw_url)]


class CoinOfferSSR(OfferStrategy):
    """عرض العملات - صفحة SSR"""

    def __init__(self):
        super().__init__("coin_ssr", "🪙 عرض العملات")

    def build_urls(self, base_url: str, product_id: str) -> list[str]:
        raw_url = ("https://m.aliexpress.com/p/coin-index/index.html"
                   f"?_immersiveMode=true&from=syicon&productIds={product_id}")
        return [raw_url]


class BundlesOfferStandard(OfferStrategy):
    """عروض الحزم - رابط قياسي"""

    def __init__(self):
        super().__init__("bundles_standard", "💰 عرض الحزم")

    def build_urls(self, base_url: str, product_id: str) -> list[str]:
        raw_url = f"{base_url}?sourceType=680&channel=bundles&afSmartRedirect=y"
        return [_wrap_url_with_star_aliexpress(raw_url)]


class BundlesOfferSSR(OfferStrategy):
    """عروض الحزم - صفحة SSR"""

    def __init__(self):
        super().__init__("bundles_ssr", "💰 عرض الحزم")

    def build_urls(self, base_url: str, product_id: str) -> list[str]:
        raw_url = (
            f"https://www.aliexpress.com/ssr/300000512/BundleDeals2"
            f"?disableNav=YES&pha_manifest=ssr&_immersiveMode=true&productIds={product_id}"
        )
        return [_wrap_url_with_star_aliexpress(raw_url)]


class StaticOffer(OfferStrategy):
    """
    استراتيجية عامة لعروض ثابتة يتم توليدها باستخدام باراميترات معينة.
    """

    def __init__(self, offer_key: str, label: str, params: dict):
        self.params = params
        super().__init__(offer_key, label)

    def build_urls(self, base_url: str, product_id: str) -> list[str]:
        query = urlencode(self.params)
        raw_url = f"{base_url}?{query}"
        return [_wrap_url_with_star_aliexpress(raw_url)]
