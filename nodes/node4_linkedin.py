import json
import re
import urllib.parse

import requests
from openai import OpenAI

from config import NVIDIA_API_KEY, NVIDIA_BASE_URL, NVIDIA_MODEL
from utils.rate_limiter import polite_delay
from utils.validator import clean_domain, extract_linkedin_urls, is_valid_linkedin_url

client = OpenAI(
    api_key=NVIDIA_API_KEY,
    base_url=NVIDIA_BASE_URL,
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_SEARCH_ENGINES = {
    "duckduckgo": "https://html.duckduckgo.com/html/?q={query}",
    "bing":       "https://www.bing.com/search?q={query}&count=10&setlang=en",
    "google":     "https://www.google.com/search?q={query}&num=10&hl=en",
}


# ──────────────────────────────────────────────────────────────
#  Search helpers
# ──────────────────────────────────────────────────────────────

def _normalize_linkedin_url(url: str) -> str | None:
    if not url:
        return None
    cleaned = url.split("?", 1)[0].split("&", 1)[0].rstrip("/")
    if not cleaned.startswith("http"):
        cleaned = f"https://{cleaned.lstrip('/')}"
    return cleaned if is_valid_linkedin_url(cleaned) else None


def _search_engine(query: str, engine: str, template: str) -> str:
    """Run one search and return raw text. Returns empty string on failure."""
    try:
        polite_delay()
        url = template.format(query=urllib.parse.quote_plus(query))
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s{2,}", " ", text).strip()
        return text[:3000]
    except Exception as exc:
        print(f"  [Node 4] {engine} failed: {exc}")
        return ""


def _collect_search_results(full_name: str, domain: str) -> tuple[list[str], str]:
    """
    Run multiple queries across search engines.
    Returns (linkedin_urls_found, raw_text_for_ai).
    """
    company = clean_domain(domain).split(".")[0].replace("-", " ")

    queries = [
        f'"{full_name}" site:linkedin.com/in "{company}"',
        f'"{full_name}" site:linkedin.com/in "{domain}"',
        f'"{full_name}" linkedin "{company}" CEO founder',
        f'"{full_name}" site:linkedin.com/in',
    ]

    all_urls: list[str] = []
    all_text = ""

    for engine_name, template in _SEARCH_ENGINES.items():
        for query in queries:
            text = _search_engine(query, engine_name, template)
            if not text:
                continue
            all_text += f"\n[{engine_name} | {query}]\n{text[:1000]}\n"
            found = extract_linkedin_urls(text)
            all_urls.extend(found)
            if len(all_urls) >= 6:
                break
        if len(all_urls) >= 6:
            break

    seen = set()
    clean_urls = []
    for url in all_urls:
        normalized = _normalize_linkedin_url(url)
        if normalized and normalized not in seen:
            seen.add(normalized)
            clean_urls.append(normalized)

    return clean_urls, all_text[:5000]


# ──────────────────────────────────────────────────────────────
#  AI LinkedIn picker
# ──────────────────────────────────────────────────────────────

def _ai_pick_linkedin(
    full_name: str,
    domain: str,
    role: str | None,
    candidate_urls: list[str],
    raw_text: str,
) -> str | None:
    """
    Ask the AI to pick the single most likely LinkedIn profile URL
    for this specific person from the candidates found.
    """
    if not candidate_urls and not raw_text:
        return None

    if not NVIDIA_API_KEY or NVIDIA_API_KEY == "your_nvidia_key_here":
        return candidate_urls[0] if candidate_urls else None

    prompt = f"""You are a B2B research assistant helping verify LinkedIn profile URLs.

Target person:
- Full name:   {full_name}
- Job role:    {role or "unknown"}
- Company:     {domain}

Candidate LinkedIn URLs found:
{json.dumps(candidate_urls, indent=2)}

Search result snippets (for context):
{raw_text[:3000]}

TASK:
Pick the single LinkedIn profile URL that most likely belongs to {full_name} at {domain}.

RULES:
- Only pick from the candidate URLs listed above
- Match the name in the URL slug to the person's name (e.g. john-smith for John Smith)
- If the role or company name appears near the URL in the snippets, that is a strong signal
- If no candidate is a good match, return null
- Return ONLY valid JSON, no explanation

JSON format:
{{
  "linkedin": "https://linkedin.com/in/... or null",
  "reason":   "one sentence explanation"
}}"""

    try:
        polite_delay()
        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()
        result = json.loads(raw)
        linkedin = result.get("linkedin")
        if linkedin and is_valid_linkedin_url(linkedin):
            print(f"  [Node 4] AI picked: {linkedin} — {result.get('reason', '')}")
            return linkedin
    except Exception as exc:
        print(f"  [Node 4] AI picker failed: {exc}")

    return candidate_urls[0] if candidate_urls else None


# ──────────────────────────────────────────────────────────────
#  Main entry point
# ──────────────────────────────────────────────────────────────

def search_linkedin_profile(
    full_name: str | None,
    domain: str,
    existing_linkedin: str | None = None,
    role: str | None = None,
) -> dict:
    """
    Node 4 - AI-Powered LinkedIn Profile Search

    1. If a valid LinkedIn URL is already known, returns it immediately.
    2. Runs multi-engine web searches for the person's LinkedIn profile.
    3. Collects all candidate URLs found.
    4. Uses NVIDIA AI to pick the single most accurate match.
    """

    if existing_linkedin and is_valid_linkedin_url(existing_linkedin):
        normalized = _normalize_linkedin_url(existing_linkedin)
        if normalized:
            return {
                "name":     full_name,
                "role":     role,
                "email":    None,
                "linkedin": normalized,
                "source":   "existing",
            }

    if not full_name:
        return {
            "name":     None,
            "role":     None,
            "email":    None,
            "linkedin": None,
            "source":   "missing_name",
        }

    print(f"  [Node 4] Searching LinkedIn for: {full_name} @ {domain}")

    candidate_urls, raw_text = _collect_search_results(full_name, domain)
    print(f"  [Node 4] Found {len(candidate_urls)} LinkedIn candidate(s)")

    if not candidate_urls:
        return {
            "name":     full_name,
            "role":     role,
            "email":    None,
            "linkedin": None,
            "source":   "not_found",
        }

    best_url = _ai_pick_linkedin(full_name, domain, role, candidate_urls, raw_text)

    return {
        "name":     full_name,
        "role":     role,
        "email":    None,
        "linkedin": best_url,
        "source":   "ai_search" if best_url else "not_found",
    }
