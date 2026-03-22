from scrapling.fetchers import DynamicFetcher
from utils.rate_limiter import polite_delay, node_wait
from utils.validator import is_valid_linkedin_url, extract_emails
import urllib.parse

fetcher = DynamicFetcher()


def find_email_from_linkedin(linkedin_url: str) -> dict:
    """
    Node 5 - Mailmeteor LinkedIn Email Finder
    Passes LinkedIn profile URL to Mailmeteor's LinkedIn-specific finder.
    Handles both found and not-found responses.
    """
    if not is_valid_linkedin_url(linkedin_url):
        return {"email": None, "status": "not_found"}

    encoded = urllib.parse.quote(linkedin_url, safe="")
    url = (
        "https://mailmeteor.com/tools/linkedin-email-finder"
        f"?linkedin-url={encoded}"
    )

    try:
        polite_delay()
        page = fetcher.fetch(url, headless=True, network_idle=True)
        node_wait()

        text = page.get_all_text(separator=" ", strip=True).lower()
        html = str(page.html_content)

        no_result_signals = [
            "no results found",
            "couldn't find an email",
            "try another one",
            "0 results",
        ]
        if any(s in text for s in no_result_signals):
            return {"email": None, "status": "not_found"}

        emails = extract_emails(text + html)
        if emails:
            return {"email": emails[0], "status": "found"}

        return {"email": None, "status": "not_found"}

    except Exception as exc:
        print(f"  [Node 5] Failed: {exc}")
        return {"email": None, "status": "not_found"}
