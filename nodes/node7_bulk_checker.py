import time
import urllib.parse

from scrapling.fetchers import Fetcher, DynamicFetcher

_DELAY_BETWEEN_CHECKS = 8
_MAX_CHECKS = 12

_static_fetcher  = Fetcher()
_dynamic_fetcher = DynamicFetcher()


def _check_one_email(email: str) -> dict:
    """
    Opens https://mailmeteor.com/email-checker?email=<encoded>
    using a lightweight static fetcher first.
    Falls back to dynamic (JS) fetcher only if static gives no result.

    Returns dict with keys:
        email    - the email checked
        overall  - valid / invalid / unknown
        format   - valid / invalid / unknown
        mailbox  - valid / invalid / unknown
    """
    encoded = urllib.parse.quote(email, safe="")
    url = f"https://mailmeteor.com/email-checker?email={encoded}"

    result = {
        "email":   email,
        "overall": "unknown",
        "format":  "unknown",
        "mailbox": "unknown",
    }

    def _parse(text: str) -> dict:
        lower = text.lower()

        if "is a valid email" in lower:
            result["overall"] = "valid"
        elif "is not a valid email" in lower or "invalid email" in lower:
            result["overall"] = "invalid"
        elif "invalid" in lower:
            result["overall"] = "invalid"

        def _field(keyword: str) -> str:
            idx = lower.find(keyword.lower())
            if idx == -1:
                return "unknown"
            snippet = lower[idx: idx + 200]
            if "invalid" in snippet:
                return "invalid"
            if "valid" in snippet:
                return "valid"
            return "unknown"

        result["format"]  = _field("format")
        result["mailbox"] = _field("mailbox")
        return result

    # ── Try static fetcher first (no JS engine, very light) ───
    try:
        page = _static_fetcher.get(
            url,
            timeout=12,
            stealthy_headers=True,
        )
        text = page.get_all_text(separator=" ", strip=True)

        if "valid email" in text.lower() or "invalid" in text.lower():
            return _parse(text)

    except Exception as exc:
        print(f"  [Node 7] Static fetch failed for {email}: {exc}")

    # ── Fall back to dynamic fetcher (JS rendered) ─────────────
    try:
        page = _dynamic_fetcher.fetch(
            url,
            headless=True,
            network_idle=True,
        )
        text = page.get_all_text(separator=" ", strip=True)
        return _parse(text)

    except Exception as exc:
        print(f"  [Node 7] Dynamic fetch also failed for {email}: {exc}")

    return result


def bulk_check_emails(email_candidates: list[str]) -> dict:
    """
    Node 7 - Bulk Email Checker

    Takes the list of generated email patterns from Node 6.
    Checks each one against mailmeteor.com/email-checker sequentially
    with delays between requests to avoid being blocked.

    Stops early as soon as a 'valid' result is found.
    If none are valid, returns the best 'unknown' result found.

    Returns dict with keys:
        email    - best email found (or None)
        overall  - valid / invalid / unknown
        format   - valid / invalid / unknown
        mailbox  - valid / invalid / unknown
        checked  - how many emails were checked
    """
    if not email_candidates:
        return {
            "email":   None,
            "overall": "none",
            "format":  "",
            "mailbox": "",
            "checked": 0,
        }

    to_check = email_candidates[:_MAX_CHECKS]
    best_unknown: dict | None = None
    checked = 0

    print(f"  [Node 7] Checking {len(to_check)} email pattern(s)...")

    for i, email in enumerate(to_check):
        print(f"  [Node 7] [{i+1}/{len(to_check)}] Checking {email}...")

        result = _check_one_email(email)
        checked += 1

        print(f"  [Node 7]   → {result['overall'].upper()}")

        if result["overall"] == "valid":
            print(f"  [Node 7] ✓ Valid email found: {email}")
            result["checked"] = checked
            return result

        if result["overall"] == "unknown" and best_unknown is None:
            best_unknown = result

        if i < len(to_check) - 1:
            print(f"  [Node 7]   Waiting {_DELAY_BETWEEN_CHECKS}s before next check...")
            time.sleep(_DELAY_BETWEEN_CHECKS)

    fallback = best_unknown or {
        "email":   None,
        "overall": "not_found",
        "format":  "",
        "mailbox": "",
    }
    fallback["checked"] = checked

    print(f"  [Node 7] No valid email found after checking {checked} pattern(s)")
    return fallback
