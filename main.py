import csv
import os
import sys

import pandas as pd
from tqdm import tqdm

from config import OUTPUT_FILE
from nodes.node1_scraper import scrape_website
from nodes.node2_ai_extractor import extract_decision_maker
from nodes.node3_mm_finder import find_email_mailmeteor
from nodes.node4_linkedin import search_linkedin_profile
from nodes.node5_mm_linkedin import find_email_from_linkedin
from nodes.node6_email_generator import generate_email_patterns
from nodes.node7_bulk_checker import bulk_check_emails
from nodes.node8_verifier import verify_email_detailed
from utils.cache import load_cache, load_progress, save_cache, save_progress
from utils.logger import done, found, node_report, node_start, not_found, section, skip, verified
from utils.rate_limiter import url_wait
from utils.validator import (
    clean_domain,
    confidence_from_node,
    email_matches_person_name,
    is_generic_role_email,
    is_valid_email,
    rank_emails,
)

RESULT_COLUMNS = [
    "domain",
    "name",
    "role",
    "linkedin",
    "email",
    "found_in_node",
    "confidence",
    "format",
    "professional",
    "domain_check",
    "mailbox",
    "overall",
    "node_summary",
]

NODE_ROLES = {
    1: "Scrape website pages for raw text, emails, and LinkedIn links",
    2: "Web research + AI to identify the decision-maker name, role, and email",
    3: "Use Mailmeteor + Hunter.io with name + domain to find a work email",
    4: "AI-powered LinkedIn profile search using multi-engine research",
    5: "Use Mailmeteor LinkedIn email finder",
    6: "Generate bulk email pattern candidates from name and domain",
    7: "Check each generated email pattern against Mailmeteor verifier",
    8: "Final detailed email verification with Mailmeteor",
}


def _normalize_url(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        return ""
    return candidate if candidate.startswith(("http://", "https://")) else f"https://{candidate}"


def _read_url_lines(source: str) -> list[str]:
    if source.lower().endswith(".csv"):
        with open(source, encoding="utf-8-sig", newline="") as handle:
            rows = [row[0].strip() for row in csv.reader(handle) if row]
        if rows and rows[0].strip().lower() in {"url", "urls", "domain", "website"}:
            rows = rows[1:]
        return rows
    with open(source, encoding="utf-8-sig") as handle:
        return [line.strip() for line in handle if line.strip()]


def load_urls(source: str) -> list[str]:
    raw_values = _read_url_lines(source) if os.path.exists(source) else [source]
    normalized_urls = []
    seen_domains = set()
    for value in raw_values:
        url = _normalize_url(value)
        domain = clean_domain(url)
        if not domain or domain in seen_domains:
            continue
        normalized_urls.append(url)
        seen_domains.add(domain)
    return normalized_urls


def _upsert_result(results: list[dict], row: dict) -> None:
    domain = row.get("domain")
    for index, existing in enumerate(results):
        if existing.get("domain") == domain:
            results[index] = row
            return
    results.append(row)


def _count_found(results: list[dict]) -> int:
    return sum(1 for row in results if row.get("email") not in {"", None, "not found"})


def _save_results_csv(results: list[dict]) -> None:
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    pd.DataFrame(results, columns=RESULT_COLUMNS).to_csv(OUTPUT_FILE, index=False)


def _record_node(node_trace: list[dict], node: int, status: str, detail: str) -> None:
    payload = {
        "node":   node,
        "role":   NODE_ROLES[node],
        "status": status,
        "detail": detail,
    }
    for index, existing in enumerate(node_trace):
        if existing["node"] == node:
            node_trace[index] = payload
            return
    node_trace.append(payload)


def _node_summary_text(node_trace: list[dict]) -> str:
    return " | ".join(
        f"Node {item['node']} [{item['status']}]: {item['detail']}"
        for item in node_trace
    )


def _select_named_candidate(
    emails: list[str],
    person_name: str | None,
    domain: str,
) -> str | None:
    if not person_name:
        return None
    for email in rank_emails(emails, domain):
        if not is_generic_role_email(email) and email_matches_person_name(email, person_name):
            return email
    return None


def run_pipeline(urls: list[str], resume: bool = True):
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    progress = load_progress() if resume else {"completed": [], "results": []}
    results = progress.get("results", [])
    completed_domains = set(progress.get("completed", []))

    for row in list(results):
        domain = row.get("domain")
        if domain:
            completed_domains.add(domain)

    total = len(urls)
    print(f"\n  LeadFinder - {total} URLs loaded")
    print(f"  Already completed: {len(completed_domains)}")
    print(f"  Remaining: {max(total - len(completed_domains), 0)}\n")

    for idx, url in enumerate(tqdm(urls, desc="Processing"), start=1):
        domain = clean_domain(url)
        if not domain:
            skip(f"Invalid URL - skipping {url}")
            continue

        if domain in completed_domains:
            skip(f"Cached - skipping {domain}")
            continue

        section(domain, idx, total)

        cached = load_cache(domain) if resume else None
        if cached:
            _upsert_result(results, cached)
            completed_domains.add(domain)
            progress["completed"] = sorted(completed_domains)
            progress["results"] = results
            save_progress(progress)
            _save_results_csv(results)
            continue

        email_to_verify = None
        found_in_node   = None
        node_trace      = []
        person = {
            "name":       None,
            "role":       None,
            "linkedin":   None,
            "email":      None,
            "confidence": "low",
        }

        # ── Node 1 ────────────────────────────────────────────
        node_start(1, "Scrapling website scraper")
        node1 = scrape_website(url)

        candidate_emails_node1 = []
        if node1["emails"]:
            candidate_emails_node1 = rank_emails(node1["emails"], domain)
            _record_node(node_trace, 1, "candidate",
                         f"Collected {len(candidate_emails_node1)} email candidates from website")
        else:
            _record_node(node_trace, 1, "failed",
                         "No usable emails found on priority website pages")

        # ── Node 2 ────────────────────────────────────────────
        node_start(2, "Web research + NVIDIA AI decision maker extractor")
        person = extract_decision_maker(node1, domain)

        # Merge any LinkedIn found in node1 scraping
        if not person.get("linkedin") and node1.get("linkedin_urls"):
            person["linkedin"] = node1["linkedin_urls"][0]

        print(
            f"  [person] {person.get('name') or '?'} - "
            f"{person.get('role') or '?'} [{person.get('confidence') or 'low'}]"
        )

        if person.get("name"):
            detail = f"{person.get('name')} - {person.get('role') or 'role unknown'}"
            if person.get("source"):
                detail = f"{detail} ({person['source']})"
            _record_node(node_trace, 2, "success", detail)
        else:
            _record_node(node_trace, 2, "failed",
                         "AI could not identify a clear decision-maker name")

        # Check if AI found a direct email match
        candidate_emails_node2 = []
        if person.get("email") and is_valid_email(person["email"]):
            candidate_emails_node2 = [person["email"]]

        # Try to match emails from Node 1 and Node 2 to the decision maker
        for node_num, candidates in ((1, candidate_emails_node1), (2, candidate_emails_node2)):
            matched = _select_named_candidate(candidates, person.get("name"), domain)
            if matched:
                email_to_verify = matched
                found_in_node   = node_num
                found(node_num, email_to_verify)
                _record_node(node_trace, node_num, "success",
                             f"Matched email {matched} to decision-maker name")
                break

        if not email_to_verify and (candidate_emails_node1 or candidate_emails_node2):
            skip("Emails found but none match the decision-maker name")

        # ── Node 3 ────────────────────────────────────────────
        if email_to_verify:
            _record_node(node_trace, 3, "skipped",
                         f"Skipped — Node {found_in_node} already found a matched email")
        elif person.get("name"):
            node_start(3, "Mailmeteor + Hunter.io email finder")
            result3 = find_email_mailmeteor(person["name"], domain)
            if result3 and is_valid_email(result3):
                email_to_verify = result3
                found_in_node   = 3
                found(3, email_to_verify)
                _record_node(node_trace, 3, "success",
                             f"Email finder returned {email_to_verify}")
            else:
                _record_node(node_trace, 3, "failed",
                             "Both Mailmeteor and Hunter.io returned no email")
        else:
            _record_node(node_trace, 3, "skipped",
                         "Skipped — no decision-maker name available")

        # ── Node 4 ────────────────────────────────────────────
        if email_to_verify:
            _record_node(node_trace, 4, "skipped",
                         f"Skipped — Node {found_in_node} already found a matched email")
        elif person.get("name") or person.get("linkedin"):
            node_start(4, "AI-powered LinkedIn profile search")
            linkedin_result = search_linkedin_profile(
                person.get("name"),
                domain,
                person.get("linkedin"),
                person.get("role"),
            )
            if linkedin_result.get("linkedin") and not person.get("linkedin"):
                person["linkedin"] = linkedin_result["linkedin"]
            if linkedin_result.get("name") and not person.get("name"):
                person["name"] = linkedin_result["name"]
            if linkedin_result.get("role") and not person.get("role"):
                person["role"] = linkedin_result["role"]

            if person.get("linkedin"):
                _record_node(node_trace, 4, "success",
                             f"LinkedIn profile found: {person['linkedin']}")
            else:
                _record_node(node_trace, 4, "failed",
                             "AI search did not find a LinkedIn profile")
        else:
            _record_node(node_trace, 4, "skipped",
                         "Skipped — no name or LinkedIn hint available")

        # ── Node 5 ────────────────────────────────────────────
        if email_to_verify:
            _record_node(node_trace, 5, "skipped",
                         f"Skipped — Node {found_in_node} already found a matched email")
        elif person.get("linkedin"):
            node_start(5, "Mailmeteor LinkedIn email finder")
            result5 = find_email_from_linkedin(person["linkedin"])
            if (
                result5.get("status") == "found"
                and result5.get("email")
                and is_valid_email(result5["email"])
                and email_matches_person_name(result5["email"], person.get("name"))
            ):
                email_to_verify = result5["email"]
                found_in_node   = 5
                found(5, email_to_verify)
                _record_node(node_trace, 5, "success",
                             f"LinkedIn email finder matched {email_to_verify}")
            elif result5.get("email"):
                skip("LinkedIn email finder returned an email that does not match the decision-maker")
                _record_node(node_trace, 5, "failed",
                             f"Unmatched email {result5['email']}")
            else:
                _record_node(node_trace, 5, "failed",
                             "LinkedIn email finder returned no email")
        else:
            _record_node(node_trace, 5, "skipped",
                         "Skipped — no LinkedIn profile available")

        # ── Node 6 + 7: Bulk pattern generation & checking ────
        if email_to_verify:
            _record_node(node_trace, 6, "skipped",
                         f"Skipped — Node {found_in_node} already found a matched email")
            _record_node(node_trace, 7, "skipped",
                         f"Skipped — Node {found_in_node} already found a matched email")
        elif person.get("name"):
            node_start(6, "Bulk email pattern generator")
            patterns = generate_email_patterns(person["name"], domain)

            if patterns:
                _record_node(node_trace, 6, "success",
                             f"Generated {len(patterns)} email pattern(s)")

                node_start(7, "Bulk email checker (Mailmeteor)")
                bulk_result = bulk_check_emails(patterns)

                if bulk_result.get("email") and bulk_result.get("overall") in ("valid", "unknown"):
                    email_to_verify = bulk_result["email"]
                    found_in_node   = 7
                    found(7, email_to_verify)
                    _record_node(node_trace, 7, "success",
                                 f"Bulk checker found {email_to_verify} "
                                 f"(overall={bulk_result['overall']}, "
                                 f"checked={bulk_result.get('checked', '?')})")
                else:
                    _record_node(node_trace, 7, "failed",
                                 f"No valid pattern found after checking "
                                 f"{bulk_result.get('checked', 0)} pattern(s)")
            else:
                _record_node(node_trace, 6, "failed",
                             "Could not generate patterns — name missing first/last name")
                _record_node(node_trace, 7, "skipped",
                             "Skipped — Node 6 generated no patterns")
        else:
            _record_node(node_trace, 6, "skipped",
                         "Skipped — no decision-maker name available")
            _record_node(node_trace, 7, "skipped",
                         "Skipped — no decision-maker name available")

        # ── Node 8: Final verification ─────────────────────────
        node_start(8, "Mailmeteor final email verifier")
        verification = None
        final_email  = None

        if email_to_verify:
            verification = verify_email_detailed(email_to_verify)
            verified(email_to_verify, verification)
            if verification["overall"] in {"valid", "unknown"}:
                final_email = email_to_verify
            _record_node(
                node_trace, 8,
                "success" if final_email else "failed",
                f"Verification overall={verification.get('overall', 'unknown')}",
            )
        else:
            not_found(domain)
            _record_node(node_trace, 8, "skipped",
                         "Skipped — no matched decision-maker email was found")

        node_report(sorted(node_trace, key=lambda item: item["node"]))

        row = {
            "domain":        domain,
            "name":          person.get("name", ""),
            "role":          person.get("role", ""),
            "linkedin":      person.get("linkedin", ""),
            "email":         final_email or "not found",
            "found_in_node": f"Node {found_in_node}" if found_in_node else "",
            "confidence":    confidence_from_node(found_in_node) if found_in_node else "none",
            "format":        verification.get("format", "")       if verification else "",
            "professional":  verification.get("professional", "") if verification else "",
            "domain_check":  verification.get("domain", "")       if verification else "",
            "mailbox":       verification.get("mailbox", "")      if verification else "",
            "overall":       verification.get("overall", "")      if verification else "",
            "node_summary":  _node_summary_text(
                sorted(node_trace, key=lambda item: item["node"])
            ),
        }

        _upsert_result(results, row)
        save_cache(domain, row)

        completed_domains.add(domain)
        progress["completed"] = sorted(completed_domains)
        progress["results"]   = results
        save_progress(progress)
        _save_results_csv(results)

        if idx < total:
            url_wait()

    _save_results_csv(results)
    save_progress({"completed": sorted(completed_domains), "results": results})
    done(total, _count_found(results))
    return pd.DataFrame(results, columns=RESULT_COLUMNS)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <urls.txt or urls.csv or https://example.com>")
        print("Example: python main.py leads.csv")
        sys.exit(1)

    source = sys.argv[1]
    resume = "--no-resume" not in sys.argv

    urls = load_urls(source)
    if not urls:
        print("No valid URLs found.")
        sys.exit(1)

    run_pipeline(urls, resume=resume)