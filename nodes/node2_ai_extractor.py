import json
import re
import time
import urllib.parse

import requests
from openai import OpenAI

from config import NVIDIA_API_KEY, NVIDIA_BASE_URL, NVIDIA_MODEL
from utils.rate_limiter import polite_delay

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
}


# ──────────────────────────────────────────────────────────────
#  Step 1: Active web research
# ──────────────────────────────────────────────────────────────

def _search_web(query: str, max_chars: int = 2000) -> str:
    """Try DuckDuckGo then Bing. Returns snippet text or empty string."""
    for engine, template in _SEARCH_ENGINES.items():
        try:
            polite_delay()
            url = template.format(query=urllib.parse.quote_plus(query))
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            resp.raise_for_status()
            text = re.sub(r"<[^>]+>", " ", resp.text)
            text = re.sub(r"\s{2,}", " ", text).strip()
            if len(text) > 100:
                return text[:max_chars]
        except Exception as exc:
            print(f"  [Node 2 search] {engine} failed: {exc}")
            time.sleep(1)
    return ""


def _research_domain(domain: str) -> dict:
    """
    Run targeted searches to find the decision maker and their email.
    Returns a dict with keys: snippets (str), emails_found (list), names_found (list)
    """
    company = domain.split(".")[0].replace("-", " ").replace("_", " ")

    queries = [
        f'"{domain}" CEO founder owner',
        f'"{company}" CEO founder email contact',
        f'site:{domain} CEO founder owner director',
        f'"{domain}" "@{domain}" email',
        f'"{company}" founder CEO linkedin',
    ]

    all_text = ""
    emails_found = []
    names_found = []

    email_re = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    name_re = re.compile(r"\b([A-Z][a-z]{1,20})\s+([A-Z][a-z]{1,20})(?:\s+[A-Z][a-z]{1,20})?\b")

    for query in queries:
        snippet = _search_web(query, max_chars=1500)
        if not snippet:
            continue
        all_text += f"\n[Query: {query}]\n{snippet}\n"

        found_emails = email_re.findall(snippet)
        domain_emails = [e for e in found_emails if domain in e.lower()]
        emails_found.extend(domain_emails)

        names = name_re.findall(snippet)
        for first, last in names:
            names_found.append(f"{first} {last}")

    emails_found = list(dict.fromkeys(e.lower() for e in emails_found))
    names_found = list(dict.fromkeys(names_found))[:10]

    return {
        "snippets": all_text[:6000],
        "emails_found": emails_found,
        "names_found": names_found,
    }


# ──────────────────────────────────────────────────────────────
#  Step 2: AI extraction with all context
# ──────────────────────────────────────────────────────────────

def extract_decision_maker(node1: dict, domain: str) -> dict:
    """
    Node 2 - NVIDIA AI Decision Maker Extractor

    Phase A: Actively researches the domain via web searches to find
             the decision maker name and any email addresses.
    Phase B: Combines research results with raw text from Node 1
             and asks LLaMA 3.1 70B to extract the single most senior
             decision maker with maximum confidence.
    """

    fallback = {
        "name": None,
        "role": None,
        "linkedin": None,
        "email": None,
        "confidence": "low",
        "source": "fallback",
    }

    if not NVIDIA_API_KEY or NVIDIA_API_KEY == "your_nvidia_key_here":
        print("  [Node 2] NVIDIA API key not set - using non-AI fallback")
        return fallback

    # ── Phase A: Web research ──────────────────────────────────
    print(f"  [Node 2] Researching {domain} on the web...")
    research = _research_domain(domain)

    print(f"  [Node 2] Research done — "
          f"{len(research['emails_found'])} emails, "
          f"{len(research['names_found'])} name candidates")

    # ── Combine all available context ─────────────────────────
    node1_text = node1.get("raw_text", "")[:3000]

    known_emails = list(dict.fromkeys(
        node1.get("emails", [])
        + research["emails_found"]
    ))

    known_linkedin = list(dict.fromkeys(
        node1.get("linkedin_urls", [])
    ))

    # ── Phase B: AI extraction ────────────────────────────────
    prompt = f"""You are a B2B research assistant. Your job is to identify the single most senior decision maker at a company.

Company domain: {domain}

PRIORITY ORDER (highest = most important):
CEO > Founder > Co-Founder > Owner > President > Managing Director > Director > Manager

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WEB RESEARCH RESULTS (fresh search data):
{research["snippets"]}

EMAILS FOUND DURING RESEARCH:
{json.dumps(research["emails_found"])}

NAME CANDIDATES FOUND DURING RESEARCH:
{json.dumps(research["names_found"])}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADDITIONAL DATA FROM WEBSITE SCRAPING:
Already known emails:   {json.dumps(known_emails)}
Already known LinkedIn: {json.dumps(known_linkedin)}

Raw text from website scraping:
{node1_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RULES:
- If multiple people are mentioned, pick only the most senior one
- Merge duplicate records about the same person
- For the email: only return it if it clearly belongs to this specific person
  (e.g. contains their first name, last name, or initials)
- If the email is generic (info@, contact@, hello@) return null for email
- If the email belongs to someone else entirely, return null for email
- Return ONLY valid JSON — no markdown, no explanation, no extra text

JSON format:
{{
  "name":       "Full Name or null",
  "role":       "Exact job title or null",
  "linkedin":   "linkedin.com/in/... url or null",
  "email":      "email@domain.com or null",
  "confidence": "high or medium or low",
  "source":     "brief note on where this info was found"
}}"""

    try:
        polite_delay()

        response = client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=400,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"```json|```", "", raw).strip()

        result = json.loads(raw)

        if not result.get("linkedin") and known_linkedin:
            result["linkedin"] = known_linkedin[0]

        if result.get("email"):
            print(f"  [Node 2] AI identified email: {result['email']}")

        print(f"  [Node 2] Decision maker: {result.get('name')} | "
              f"{result.get('role')} | confidence: {result.get('confidence')}")

        return result

    except json.JSONDecodeError:
        print("  [Node 2] AI returned invalid JSON — falling back")
    except Exception as exc:
        print(f"  [Node 2] Failed: {exc}")

    fallback["source"] = "failed"
    return fallback
