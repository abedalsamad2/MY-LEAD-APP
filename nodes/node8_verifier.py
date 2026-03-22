import urllib.parse

from scrapling.fetchers import DynamicFetcher
from utils.rate_limiter import node_wait, polite_delay

fetcher = DynamicFetcher()


def verify_email_detailed(email: str) -> dict:
    """
    Node 8 - Mailmeteor Email Verifier (Final)

    Visits mailmeteor.com/email-checker?email=X
    Waits for JS to render all 4 checks.
    Returns full detailed verification result.

    Result fields:
    - overall:      valid / invalid / unknown
    - format:       Is syntax correct?
    - professional: Not webmail or throwaway?
    - domain:       MX records exist?
    - mailbox:      Server confirmed inbox?
    """
    encoded = urllib.parse.quote(email)
    url = f"https://mailmeteor.com/email-checker?email={encoded}"

    try:
        polite_delay()
        page = fetcher.fetch(url, headless=True, network_idle=True)
        node_wait()

        text = page.get_all_text(separator=" ", strip=True)
        lower = text.lower()

        def check_field(keyword: str) -> str:
            idx = lower.find(keyword.lower())
            if idx == -1:
                return "unknown"
            snippet = lower[idx: idx + 200]
            if "invalid" in snippet:
                return "invalid"
            if "valid" in snippet:
                return "valid"
            return "unknown"

        if "is a valid email" in lower:
            overall = "valid"
        elif "is not a valid email" in lower or "invalid email" in lower:
            overall = "invalid"
        elif "invalid" in lower:
            overall = "invalid"
        else:
            overall = "unknown"

        return {
            "email":        email,
            "overall":      overall,
            "format":       check_field("format"),
            "professional": check_field("professional"),
            "domain":       check_field("domain status"),
            "mailbox":      check_field("mailbox"),
        }

    except Exception as exc:
        print(f"  [Node 8] Failed: {exc}")
        return {
            "email":        email,
            "overall":      "unknown",
            "format":       "unknown",
            "professional": "unknown",
            "domain":       "unknown",
            "mailbox":      "unknown",
        }
