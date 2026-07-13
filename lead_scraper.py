"""
Lead Scraper — verifies real businesses and extracts contact info.

WHAT THIS DOES:
  Takes a seed list of businesses (name + website), visits each real
  website, confirms it's actually live, and scrapes the homepage plus
  common About/Team/Contact pages for email addresses and likely
  decision-maker names. Outputs a CSV with a confidence flag per row.

WHAT THIS DOES NOT DO:
  - It does not invent companies or emails. If a site is down or has no
    visible contact info, that row is marked accordingly rather than
    guessed.
  - It does not guarantee a perfect decision-maker name — it surfaces
    likely candidates (text near words like "Founder", "Director",
    "Owner") for you to glance at and confirm, since name extraction
    from arbitrary web pages is never 100% reliable.
  - It does not scrape Google, LinkedIn, or Yelp directly — those
    have ToS restrictions on scraping. Get seed data (name + website)
    from Google Places API, a directory export, or manual research,
    then feed it into this script.

SETUP:
  pip install requests beautifulsoup4

USAGE:
  1. Fill in SEED_LEADS below (or load from a CSV — see load_seed_csv()).
  2. Run: python lead_scraper.py
  3. Check output/verified_leads.csv

Rate-limited to be a polite scraper: one request at a time, small delay
between sites, respects a short timeout so one dead site doesn't hang
the whole run.
"""

import csv
import re
import time
import sys
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT = 8            # seconds — don't let one dead site hang the run
DELAY_BETWEEN_SITES = 1.5      # seconds — be a polite scraper, not a hammer
USER_AGENT = (
    "Mozilla/5.0 (compatible; LeadResearchBot/1.0; "
    "+contact: youremail@example.com)"  # <-- put your real contact here.
    # Identifying your bot honestly is good scraping etiquette and makes
    # it easy for a site owner to ask you to stop if they want to.
)

COMMON_SUBPAGES = [
    "about", "about-us", "team", "our-team", "meet-the-team",
    "contact", "contact-us", "who-we-are",
]

TITLE_KEYWORDS = [
    "founder", "owner", "director", "managing partner", "principal",
    "ceo", "managing director", "proprietor", "partner",
]

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Skip obvious junk matches (image filenames, tracking pixels, etc.)
EMAIL_BLOCKLIST_DOMAINS = {"example.com", "sentry.io", "wixpress.com"}


@dataclass
class LeadResult:
    name: str
    seed_website: str
    site_reachable: bool = False
    final_url: str = ""
    emails_found: list = field(default_factory=list)
    candidate_names: list = field(default_factory=list)
    pages_checked: list = field(default_factory=list)
    notes: str = ""


def fetch(url: str):
    """Fetch a URL politely; return (success, response_or_None)."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        if resp.status_code < 400:
            return True, resp
        return False, resp
    except requests.RequestException:
        return False, None


def extract_emails(html_text: str):
    found = set()
    for match in EMAIL_REGEX.findall(html_text):
        domain = match.split("@")[-1].lower()
        if domain in EMAIL_BLOCKLIST_DOMAINS:
            continue
        if match.lower().endswith((".png", ".jpg", ".gif")):
            continue
        found.add(match)
    return sorted(found)


def extract_candidate_names(soup: BeautifulSoup):
    """
    Heuristic only: look for short text blocks containing a title keyword
    (e.g. "Founder") and pull nearby capitalized word-pairs as a likely
    name. This WILL miss some real names and WILL occasionally grab noise
    — treat every result as "worth a human glance", not a confirmed fact.
    """
    candidates = set()
    text_blocks = soup.find_all(["p", "h1", "h2", "h3", "h4", "li", "span", "div"])
    name_pattern = re.compile(r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2})\b")

    for block in text_blocks:
        text = block.get_text(" ", strip=True)
        if not text or len(text) > 300:
            continue
        lowered = text.lower()
        if any(kw in lowered for kw in TITLE_KEYWORDS):
            for name_match in name_pattern.findall(text):
                # Filter out common false positives
                if name_match.lower() in {"contact us", "about us", "read more"}:
                    continue
                candidates.add(name_match)

    return sorted(candidates)


def check_lead(name: str, website: str) -> LeadResult:
    result = LeadResult(name=name, seed_website=website)

    if not website.startswith("http"):
        website = "https://" + website

    ok, resp = fetch(website)
    if not ok or resp is None:
        result.notes = "Site unreachable — do not send outreach to this domain."
        return result

    result.site_reachable = True
    result.final_url = resp.url
    result.pages_checked.append(resp.url)

    soup = BeautifulSoup(resp.text, "html.parser")
    result.emails_found.extend(extract_emails(resp.text))
    result.candidate_names.extend(extract_candidate_names(soup))

    # Try a few common subpages for team/contact info
    base = f"{urlparse(resp.url).scheme}://{urlparse(resp.url).netloc}"
    for slug in COMMON_SUBPAGES:
        sub_url = urljoin(base + "/", slug)
        time.sleep(0.5)
        sub_ok, sub_resp = fetch(sub_url)
        if sub_ok and sub_resp is not None:
            result.pages_checked.append(sub_url)
            sub_soup = BeautifulSoup(sub_resp.text, "html.parser")
            result.emails_found.extend(extract_emails(sub_resp.text))
            result.candidate_names.extend(extract_candidate_names(sub_soup))

    result.emails_found = sorted(set(result.emails_found))
    result.candidate_names = sorted(set(result.candidate_names))

    if not result.emails_found and not result.candidate_names:
        result.notes = "Site is live but no email/name found automatically — check manually."
    else:
        result.notes = "OK"

    return result


def load_seed_csv(path: str):
    """
    Load seed leads from a CSV with columns: name, website
    (Grab this from Google Places results, a directory export, etc.)
    """
    leads = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("name") and row.get("website"):
                leads.append((row["name"].strip(), row["website"].strip()))
    return leads


# ---------------------------------------------------------------------------
# EDIT THIS: your seed list, OR call load_seed_csv("your_file.csv") instead
# ---------------------------------------------------------------------------
SEED_LEADS = [
    ("Naseems Accountants", "naseemsaccountants.co.uk"),
    ("Gondal Accountancy", "gondalaccountancy.co.uk"),
    ("Agile Accountants", "agileaccountants.co.uk"),
    # Add more (name, website) pairs here, or use load_seed_csv() below.
]


def main():
    leads = SEED_LEADS
    # To use a CSV instead, comment the line above and uncomment:
    # leads = load_seed_csv("seed_leads.csv")

    if not leads:
        print("No seed leads provided. Fill in SEED_LEADS or provide a CSV.")
        sys.exit(1)

    results = []
    for i, (name, website) in enumerate(leads, 1):
        print(f"[{i}/{len(leads)}] Checking {name} ({website})...")
        result = check_lead(name, website)
        results.append(result)
        time.sleep(DELAY_BETWEEN_SITES)

    out_path = "verified_leads.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "name", "seed_website", "site_reachable", "final_url",
            "emails_found", "candidate_names", "notes",
        ])
        for r in results:
            writer.writerow([
                r.name,
                r.seed_website,
                r.site_reachable,
                r.final_url,
                "; ".join(r.emails_found),
                "; ".join(r.candidate_names),
                r.notes,
            ])

    reachable = sum(1 for r in results if r.site_reachable)
    with_contact = sum(1 for r in results if r.emails_found or r.candidate_names)
    print(f"\nDone. {reachable}/{len(results)} sites reachable, "
          f"{with_contact}/{len(results)} had some contact info found.")
    print(f"Results written to {out_path}")


if __name__ == "__main__":
    main()
