import re
from urllib.parse import urlparse

EMAIL_RE = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
LINKEDIN_RE = r"https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-_%]+/?"
PLACEHOLDER_LOCAL_PARTS = {
    "email", "example", "firstname", "lastname",
    "mail", "name", "sample", "test", "user", "yourname",
}
PLACEHOLDER_DOMAINS = {
    "domain.com", "email.com", "example.com",
    "example.org", "test.com", "yourdomain.com",
}
GENERIC_LOCAL_PARTS = {
    "admin", "billing", "careers", "contact", "customerservice",
    "hello", "help", "info", "jobs", "office",
    "sales", "service", "support", "team",
}
REGISTRAR_OR_INFRA_DOMAINS = {
    "godaddy.com", "domainsbyproxy.com", "enom.com", "godaddy.org",
    "hostgator.com", "networksolutions.com", "privacyguardian.org",
    "register.com", "whoisprivacyprotect.com",
}


def is_valid_email(email: str) -> bool:
    if not email:
        return False
    candidate = email.strip().lower()
    if not re.fullmatch(EMAIL_RE, candidate):
        return False
    return not is_placeholder_email(candidate)


def is_valid_linkedin_url(url: str) -> bool:
    if not url:
        return False
    return bool(re.fullmatch(LINKEDIN_RE, url.strip()))


def clean_domain(url: str) -> str:
    if not url:
        return ""
    candidate = url.strip()
    parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
    domain = parsed.netloc or parsed.path.split("/")[0]
    domain = domain.split("@")[-1].split(":")[0].lower()
    return domain.removeprefix("www.")


def extract_emails(text: str) -> list[str]:
    return sorted(set(re.findall(EMAIL_RE, text or "")))


def extract_linkedin_urls(text: str) -> list[str]:
    return sorted(set(re.findall(LINKEDIN_RE, text or "")))


def email_matches_domain(email: str, domain: str) -> bool:
    if not email or not domain or "@" not in email:
        return False
    email_domain = email.rsplit("@", 1)[-1].lower()
    target = clean_domain(domain)
    return email_domain == target or email_domain.endswith(f".{target}")


def is_placeholder_email(email: str) -> bool:
    if not email or "@" not in email:
        return True
    local_part, domain = email.strip().lower().rsplit("@", 1)
    if domain in PLACEHOLDER_DOMAINS:
        return True
    if local_part in PLACEHOLDER_LOCAL_PARTS:
        return True
    if any(token in local_part for token in {"example", "test", "your", "dummy"}):
        return True
    return False


def rank_emails(emails: list[str], domain: str | None = None) -> list[str]:
    valid_emails = []
    seen = set()
    for email in emails:
        normalized = (email or "").strip().lower()
        if normalized in seen or not is_valid_email(normalized):
            continue
        seen.add(normalized)
        valid_emails.append(normalized)
    if not domain:
        return valid_emails
    return sorted(
        valid_emails,
        key=lambda email: (
            0 if email_matches_domain(email, domain) else 1,
            email,
        ),
    )


def is_generic_role_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    local_part = email.strip().lower().split("@", 1)[0]
    normalized = re.sub(r"[^a-z]", "", local_part)
    return normalized in GENERIC_LOCAL_PARTS


def email_matches_person_name(email: str, full_name: str | None) -> bool:
    if not email or not full_name or "@" not in email:
        return False
    local_part = email.strip().lower().split("@", 1)[0]
    normalized_local = re.sub(r"[^a-z]", "", local_part)
    name_parts = [
        re.sub(r"[^a-z]", "", part.lower())
        for part in full_name.split()
        if re.sub(r"[^a-z]", "", part.lower())
    ]
    if not name_parts:
        return False
    first = name_parts[0]
    last = name_parts[-1] if len(name_parts) > 1 else ""
    combos = {
        first, last,
        f"{first}{last}" if last else first,
        f"{first}.{last}" if last else first,
        f"{first}_{last}" if last else first,
        f"{first[0]}{last}" if first and last else "",
        f"{first}{last[0]}" if first and last else "",
    }
    combos = {re.sub(r"[^a-z]", "", combo) for combo in combos if combo}
    if normalized_local in combos:
        return True
    if first and first in normalized_local and last and last in normalized_local:
        return True
    if last and normalized_local.endswith(last) and first and normalized_local.startswith(first[:1]):
        return True
    return False


def is_registrar_or_infrastructure_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    domain = email.strip().lower().rsplit("@", 1)[-1]
    return domain in REGISTRAR_OR_INFRA_DOMAINS


def pick_best_email(
    emails: list[str],
    domain: str | None = None,
    prefer_personal: bool = False,
) -> str | None:
    ranked = rank_emails(emails, domain)
    if not ranked:
        return None
    if prefer_personal:
        for email in ranked:
            if not is_generic_role_email(email):
                return email
        return None
    return ranked[0]


def confidence_from_node(node: int | None) -> str:
    """Map new node numbers to confidence levels."""
    map_ = {
        1: "very_high",  # found directly on website
        2: "high",       # AI + web research found it
        3: "high",       # Mailmeteor / Hunter found it
        4: "high",       # LinkedIn profile search led to it
        5: "high",       # Mailmeteor LinkedIn finder
        6: "medium",     # pattern generator (shouldn't find email directly)
        7: "medium",     # bulk pattern checker
    }
    return map_.get(node, "low")
