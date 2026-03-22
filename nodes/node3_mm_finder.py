import urllib.parse

import requests
from scrapling.fetchers import DynamicFetcher
from tenacity import retry, stop_after_attempt, wait_fixed

from config import MAX_RETRIES, RETRY_WAIT
from utils.rate_limiter import node_wait, polite_delay
from utils.validator import email_matches_domain, extract_emails

fetcher = DynamicFetcher()

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ──────────────────────────────────────────────────────────────
#  Source 1: Mailmeteor Email Finder
# ──────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_fixed(RETRY_WAIT))
def _try_mailmeteor(full_name: str, domain: str) -> str | None:
    """
    Visits mailmeteor.com/tools/email-finder?name=...&domain=...
    Uses DynamicFetcher to wait for JS to render the result.
    """
    name_encoded = full_name.strip().lower().replace(" ", "+")
    url = (
        "https://mailmeteor.com/tools/email-finder"
        f"?name={name_encoded}&domain={domain}"
    )

    try:
        polite_delay()
        page = fetcher.fetch(url, headless=True, network_idle=True)
        node_wait()

        text = page.get_all_text(separator=" ", strip=True)
        html = str(page.html_content)
        emails = [
            e for e in extract_emails(text + html)
            if email_matches_domain(e, domain)
        ]
        if emails:
            print(f"  [Node 3] Mailmeteor found: {emails[0]}")
            return emails[0]

    except Exception as exc:
        print(f"  [Node 3] Mailmeteor failed: {exc}")

    return None


# ──────────────────────────────────────────────────────────────
#  Source 2: Hunter.io Email Finder
# ──────────────────────────────────────────────────────────────

def _try_hunter(full_name: str, domain: str) -> str | None:
    """
    Visits hunter.io/find/{domain}/{name_encoded}
    Example: https://hunter.io/find/membershipbespoke.com/dennis%20howes
    Uses DynamicFetcher because the result is JS-rendered.
    """
    name_encoded = urllib.parse.quote(full_name.strip())
    url = f"https://hunter.io/find/{domain}/{name_encoded}"

    try:
        polite_delay()
        page = fetcher.fetch(url, headless=True, network_idle=True)
        node_wait()

        text = page.get_all_text(separator=" ", strip=True)
        html = str(page.html_content)

        emails = [
            e for e in extract_emails(text + html)
            if email_matches_domain(e, domain)
        ]

        if emails:
            print(f"  [Node 3] Hunter.io found: {emails[0]}")
            return emails[0]

        if "%" in text:
            print(f"  [Node 3] Hunter.io returned result but no parseable email")

    except Exception as exc:
        print(f"  [Node 3] Hunter.io failed: {exc}")

    return None


# ──────────────────────────────────────────────────────────────
#  Main entry point
# ──────────────────────────────────────────────────────────────

def find_email_mailmeteor(full_name: str, domain: str) -> str | None:
    """
    Node 3 - Email Finder (Mailmeteor + Hunter.io fallback)

    1. Tries Mailmeteor email finder first.
    2. If Mailmeteor fails or returns nothing, tries Hunter.io.
    3. Returns the first valid matching email found, or None.
    """
    if not full_name or not domain:
        return None

    # Source 1: Mailmeteor
    email = _try_mailmeteor(full_name, domain)
    if email:
        return email

    print(f"  [Node 3] Mailmeteor returned nothing — trying Hunter.io...")

    # Source 2: Hunter.io
    email = _try_hunter(full_name, domain)
    if email:
        return email

    print(f"  [Node 3] Both sources failed for {full_name} @ {domain}")
    return None
