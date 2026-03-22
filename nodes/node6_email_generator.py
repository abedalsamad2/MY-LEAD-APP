import re


def _clean(text: str) -> str:
    """Lowercase and remove non-alpha characters."""
    return re.sub(r"[^a-z]", "", text.lower().strip())


def generate_email_patterns(full_name: str, domain: str) -> list[str]:
    """
    Node 6 - Bulk Email Pattern Generator

    Given a person's full name and company domain, generates all common
    corporate email format combinations used by real businesses.

    Returns a deduplicated ordered list of candidate emails,
    most common patterns first.
    """
    if not full_name or not domain:
        return []

    parts = full_name.strip().split()
    if len(parts) < 2:
        first = _clean(parts[0])
        last = ""
    else:
        first = _clean(parts[0])
        last  = _clean(parts[-1])

    fi = first[0] if first else ""
    li = last[0]  if last  else ""

    d = domain.lower().strip()

    patterns = []

    if first and last:
        patterns = [
            f"{first}@{d}",
            f"{first}.{last}@{d}",
            f"{fi}{last}@{d}",
            f"{first}{last}@{d}",
            f"{first}_{last}@{d}",
            f"{first}-{last}@{d}",
            f"{last}@{d}",
            f"{last}.{first}@{d}",
            f"{last}{first}@{d}",
            f"{last}_{first}@{d}",
            f"{fi}.{last}@{d}",
            f"{first}.{li}@{d}",
            f"{first}{li}@{d}",
            f"{fi}{li}@{d}",
            f"{last}.{fi}@{d}",
            f"{last}{fi}@{d}",
            f"{first[0:2]}{last}@{d}",
            f"{first}{last[0:2]}@{d}",
        ]
    elif first:
        patterns = [f"{first}@{d}"]

    seen = set()
    result = []
    for email in patterns:
        if email not in seen:
            seen.add(email)
            result.append(email)

    print(f"  [Node 6] Generated {len(result)} email pattern(s) for "
          f"{full_name} @ {domain}")

    return result
