# constants.py
from offers import (CoinOfferProductView, CoinOfferSSR, BundlesOfferStandard,
                    BundlesOfferSSR, StaticOffer)

# --- Offer Parameter Mapping ---

OFFERS = [
    CoinOfferSSR(),
    StaticOffer("super", "🔥 عروض السوبر", {
        "sourceType": "562",
        "channel": "sd",
        "afSmartRedirect": "y"
    }),
    StaticOffer("bundels", "🎁 الحزم مباشرة", {
        "sourceType": "570",
        "channel": "bundles",
        "afSmartRedirect": "y"
    }),
    BundlesOfferSSR()
]

OFFER_ORDER = [o.offer_key for o in OFFERS]
OFFER_PARAMS = {o.offer_key: o for o in OFFERS}
"""
#CoinOfferProductView(),

#BundlesOfferStandard(),


StaticOffer("bigsave", "💰 Big Save", {
    "sourceType": "680",
    "channel": "bigSave",
    "afSmartRedirect": "y"
}),

StaticOffer("limited", "⏳ Limited Offers", {
    "sourceType": "561",
    "channel": "limitedoffers",
    "afSmartRedirect": "y"
}),
"""
