from scrapling.fetchers import Fetcher
from utils.rate_limiter import polite_delay
from utils.validator import clean_domain, extract_emails, extract_linkedin_urls, rank_emails
from config import PRIORITY_PATHS

fetcher = Fetcher()

def scrape_website(base_url: str) -> dict:
    """
    Node 1 - Scrapling Website Scraper
    Visits priority pages on the business website.
    Extracts: raw text, emails, LinkedIn URLs.
    """
    result = {
        "raw_text": "",
        "emails": [],
        "linkedin_urls": [],
    }

    for path in PRIORITY_PATHS:
        try:
            polite_delay()
            page = fetcher.get(
                f"{base_url.rstrip('/')}{path}",
                timeout=10,
                stealthy_headers=True,
            )
            text = page.get_all_text(separator=" ", strip=True)
            html = str(page.html_content)

            result["raw_text"] += f"\n{text}"
            result["emails"] += extract_emails(f"{text} {html}")
            result["linkedin_urls"] += extract_linkedin_urls(html)

        except Exception:
            continue

    result["emails"] = rank_emails(result["emails"], clean_domain(base_url))
    result["linkedin_urls"] = list(set(result["linkedin_urls"]))

    return result
