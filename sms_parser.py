import re
from typing import Optional


def parse_telebirr_sms(text: str) -> Optional[dict]:
    cleaned = text.strip().replace("\n", " ").replace("\r", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)

    patterns = [
        {
            "regex": re.compile(
                r"(?:you've|you have)\s+(?:been\s+)?(?:sent|received|paid|transferred|credited)\s+"
                r"(?:ETB|birr|Br)?\s*([0-9,]+(?:\.\d{1,2})?)",
                re.IGNORECASE,
            ),
            "amount_group": 1,
            "ref_regex": re.compile(
                r"(?:transaction|reference|ref|trx?|id)\s*(?::|no|#)?\s*"
                r"([A-Za-z0-9]{6,})",
                re.IGNORECASE,
            ),
        },
        {
            "regex": re.compile(
                r"(?:amount|መጠን)\s*(?::|ብር)?\s*([0-9,]+(?:\.\d{1,2})?)",
                re.IGNORECASE,
            ),
            "amount_group": 1,
            "ref_regex": re.compile(
                r"(?:ref(?:erence)?|receipt|no|ቁጥር)\s*(?::|#)?\s*"
                r"([A-Za-z0-9]{6,})",
                re.IGNORECASE,
            ),
        },
    ]

    result = {}
    for p in patterns:
        m = p["regex"].search(cleaned)
        if m:
            amt_str = m.group(p["amount_group"]).replace(",", "")
            try:
                result["amount"] = round(float(amt_str), 2)
            except ValueError:
                continue
            ref_m = p["ref_regex"].search(cleaned)
            if ref_m:
                result["ref"] = ref_m.group(1).strip()
            break

    if "amount" not in result:
        amounts = re.findall(r"(\d+(?:\.\d{1,2})?)\s*(?:ETB|birr|Br)", cleaned, re.IGNORECASE)
        if amounts:
            try:
                result["amount"] = round(float(amounts[-1].replace(",", "")), 2)
            except ValueError:
                pass

    if "ref" not in result:
        refs = re.findall(r"[A-Za-z0-9]{8,}", cleaned)
        if refs:
            result["ref"] = refs[0]

    phone_match = re.search(
        r"(?:from|to|sender|recipient|receiver|ከ|ወደ)\s*(?::)?\s*"
        r"(?:\+251|0|251)?(91[0-9]{8}|92[0-9]{8}|93[0-9]{8}|94[0-9]{8}|95[0-9]{8}|96[0-9]{8}|97[0-9]{8}|98[0-9]{8})",
        cleaned,
        re.IGNORECASE,
    )
    if phone_match:
        phone = phone_match.group(1)
        result["phone"] = f"0{phone}" if len(phone) == 9 else phone

    name_match = re.search(
        r"(?:to|recipient|receiver|beneficiary|ወደ)\s*(?::)?\s*([A-Za-z\u1200-\u137F\s.]+?)(?:\s*(?:-|\||\d|$))",
        cleaned,
    )
    if name_match:
        result["recipient_name"] = name_match.group(1).strip()

    return result if "amount" in result else None


def verify_recipient(
    parsed: dict,
    expected_name: str,
    expected_last4: str,
    min_amount: float = 20,
    expected_amount: float = None,
) -> tuple:
    errors = []

    amount = parsed.get("amount", 0)
    if amount < min_amount:
        errors.append(f"Amount below minimum ({min_amount} ETB)")

    if expected_amount is not None and abs(amount - expected_amount) > 0.5:
        errors.append(f"amount_mismatch")

    parsed_name = parsed.get("recipient_name", "").lower().strip()
    expected_lower = expected_name.lower().strip()
    if parsed_name and expected_lower:
        name_words = set(re.findall(r"[a-z]+", parsed_name))
        exp_words = set(re.findall(r"[a-z]+", expected_lower))
        common = name_words & exp_words
        if len(common) < max(1, len(exp_words) // 2):
            errors.append("recipient_mismatch")

    parsed_phone = parsed.get("phone", "")
    if parsed_phone and not parsed_phone.endswith(expected_last4):
        errors.append("recipient_mismatch")

    ref = parsed.get("ref", "")
    if not ref:
        errors.append("invalid_sms")

    return errors, parsed
