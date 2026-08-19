import html
from urllib.parse import urlparse

from constants import OFFER_PARAMS, OFFER_ORDER

# رمز RTL لإجبار النص على الاتجاه من اليمين لليسار
rtl_mark = "\u200F"
TELEGRAM_CAPTION_MAX_LENGTH = 1024
TELEGRAM_TEXT_MAX_LENGTH = 4096
ARABIC_CURRENCY_NAMES = {
    "USD": "دولار أمريكي",
    "SAR": "ريال سعودي",
    "AED": "درهم إماراتي",
    "EGP": "جنيه مصري",
    "EUR": "يورو",
    "GBP": "جنيه إسترليني",
    "CNY": "يوان صيني",
    "ILS": "شيكل إسرائيلي",
}


def safe_html_href(url: str | None) -> str | None:
    """Escape a URL for use in an HTML href attribute, or reject it."""
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return None
    return html.escape(url, quote=True)


def format_product_message(product_info: dict, generated_links: dict) -> str:
    """تهيئة نص الرسالة لإرسالها عبر تيليجرام باللغة العربية."""
    product_title = html.escape(str(product_info.get('title') or '')[:250])
    product_price = product_info.get('price')
    product_currency = product_info.get('currency')
    details_source = product_info.get('source')

    message_lines = []
    message_lines.append(f"<b>{rtl_mark}{product_title}</b>")

    arabic_currency = ARABIC_CURRENCY_NAMES.get(product_currency, product_currency)
    safe_currency = html.escape(str(arabic_currency or ''))

    if details_source == "API" and product_price:
        price_str = f"{html.escape(str(product_price))} {safe_currency}".strip()
        message_lines.append(f"\n<b>السعر بعد الخصم:</b> {price_str}\n")
    elif details_source == "Scraped":
        message_lines.append("\n<b>السعر بعد الخصم:</b> غير متوفر\n")
    else:
        message_lines.append("\n<b>تفاصيل المنتج غير متوفرة</b>\n")

    message_lines.append("<b>العروض المتاحة:</b>")

    for offer_key in OFFER_ORDER:
        link = generated_links.get(offer_key)
        offer_name = html.escape(str(OFFER_PARAMS[offer_key].label))
        href = safe_html_href(link)
        if href:
            message_lines.append(
                f'{offer_name}: <a href="{href}">اضغط هنا</a>')
        else:
            message_lines.append(f"{offer_name}: ❌ فشل في الإنشاء")

    message_lines.append("\n<i>تم الإنشاء بواسطة P4uDeals</i>")
    return "\n".join(message_lines)


def format_no_offers_message(product_title: str) -> str:
    return (
        f"<b>{html.escape(str(product_title)[:250])}</b>\n\n"
        "لم نتمكن من العثور على عروض لهذا المنتج حاليًا ❌")


def truncate_telegram_text(text: str) -> str:
    if len(text) > TELEGRAM_TEXT_MAX_LENGTH:
        return text[:TELEGRAM_TEXT_MAX_LENGTH - 1] + "…"
    return text


def caption_fits(text: str) -> bool:
    return len(text) <= TELEGRAM_CAPTION_MAX_LENGTH
