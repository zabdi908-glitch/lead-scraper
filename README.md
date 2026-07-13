# Lead Scraper

Verifies real accounting/bookkeeping firms and pulls contact info — built to
avoid the failure mode of AI-generated lead lists that quietly invent
companies or emails to hit a requested count.

## What this does

Takes a seed list of real businesses (name + website), visits each site,
confirms it's actually live, and scrapes the homepage plus common
About/Team/Contact pages for email addresses and likely decision-maker names.
Outputs a CSV with a confidence note per row.

## What this does NOT do

- **Does not invent companies or emails.** If a site is down or has no
  visible contact info, that row is marked accordingly — never guessed.
- **Does not guarantee a perfect decision-maker name.** It surfaces likely
  candidates (text near words like "Founder", "Director", "Owner") for a
  human to glance at and confirm — name extraction from arbitrary web pages
  is never 100% reliable.
- **Does not scrape Google, LinkedIn, or Yelp directly** — those restrict
  scraping in their ToS. Get seed data (name + website) from a source like
  Google Places, a directory export, or manual research, then feed it in
  here.

## Setup

```bash
pip install requests beautifulsoup4
```

## Usage

1. Edit `seed_leads.csv` with real businesses — columns: `name,website`
2. Run:
   ```bash
   python lead_scraper.py
   ```
3. Check `verified_leads.csv` for results. The `notes` column tells you what
   to trust:
   - `OK` — email and/or name found, worth using
   - `Site is live but no email/name found automatically` — real company,
     check the site manually
   - `Site unreachable` — do not send outreach to this domain

## How the seed list gets built

This script is the *second* step, not the first — it needs a starting list
of real business names + websites. Good sources:

- Google Places API results (structured, verified by Google)
- A directory export you've manually spot-checked
- Manual research

**Do not** feed it AI-generated "give me N leads" lists without spot-checking
first — those are prone to fabricating plausible-looking companies once the
model runs out of real ones matching the count you asked for. That's exactly
the problem this script exists to catch.

## Status / next steps

- [x] Core scraping logic written
- [ ] Tested against real websites (needs to be run somewhere with actual
      internet access — the environment this was originally written in had
      none)
- [ ] Wire seed data to load from `seed_leads.csv` automatically instead of
      the hardcoded list at the bottom of the script
- [ ] Consider scheduling (e.g. via Render) once proven reliable
