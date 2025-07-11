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


"""
super offer

Resolved link: https://star.aliexpress.com/share/share.htm?platform=AE&businessType=ProductDetail&shareId=6000308646916&redirectUrl=https://www.aliexpress.com/item/1005007722296606.html?businessType%3DProductDetail%26shareId%3D6000308646916%26srcSns%3Dsns_Copy%26sourceType%3D562%26spreadType%3DsocialShare%26bizType%3DProductDetail%26social_params%3D6000308646916&aff_fcid=aa58b181aa8b4de6b1ea97cb7bad8cd0-1751208205985-04341-_oFteIuE&tt=CPS_NORMAL&aff_fsk=_oFteIuE&aff_platform=shareComponent-detail&sk=_oFteIuE&aff_trace_key=aa58b181aa8b4de6b1ea97cb7bad8cd0-1751208205985-04341-_oFteIuE&terminal_id=52ae98e8ca6e43c18f55b335cb6ad44b

3D562

coin offer direct page from phone

https://star.aliexpress.com/share/share.htm?platform=AE&businessType=ProductDetail&shareId=6000308069155&redirectUrl=https://www.aliexpress.com/item/1005006731698567.html?businessType%3DProductDetail%26shareId%3D6000308069155%26srcSns%3Dsns_Copy%26sourceType%3D620%26spreadType%3DsocialShare%26bizType%3DProductDetail%26social_params%3D6000308069155&aff_fcid=67b0ce0f818c4c82868aa82c76b49d33-1751209287830-06585-_oENkBKw&tt=CPS_NORMAL&aff_fsk=_oENkBKw&aff_platform=shareComponent-detail&sk=_oENkBKw&aff_trace_key=67b0ce0f818c4c82868aa82c76b49d33-1751209287830-06585-_oENkBKw&terminal_id=373f504a530a45e38907f6ba77f67829

sourceType%3D620

bundles offer direct page from phone

https://star.aliexpress.com/share/share.htm?platform=AE&businessType=ProductDetail&shareId=6000307125756&redirectUrl=https://www.aliexpress.com/item/1005006967262943.html?businessType%3DProductDetail%26shareId%3D6000307125756%26srcSns%3Dsns_Copy%26sourceType%3D570%26spreadType%3DsocialShare%26bizType%3DProductDetail%26social_params%3D6000307125756&aff_fcid=43107736d18645c7b7cee126f086f0d6-1751209814324-08503-_omEfwjY&tt=CPS_NORMAL&aff_fsk=_omEfwjY&aff_platform=shareComponent-detail&sk=_omEfwjY&aff_trace_key=43107736d18645c7b7cee126f086f0d6-1751209814324-08503-_omEfwjY&terminal_id=9923dd2bc3ac4ade9a714c52c6dba834

sourceType%3D570


"""
