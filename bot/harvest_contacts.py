"""
Harvest CRE contacts from ProVisors Hub member directory.
Navigates through the Hub's multi-step member search form:
  /membersearch → click "Member Search" → /member-directory form

Each result page has 10 card-detail blocks per page with fields:
  Member Info (name link), Profession, Professional Focus,
  Email, Company, Home Group, Groups, Short Bio

Run monthly: python bot/harvest_contacts.py
Then embed:  python bot/embed_contacts.py
Then deploy: FORCE_TTY=1 npx vercel --prod --yes
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import asyncio
from pathlib import Path
from datetime import datetime
from hub_bot import HubBot

# Profession dropdown values from the Hub form (CRE-relevant ones)
PROFESSIONS = [
    "Real Estate",
    "Banking & Finance",
    "Attorney",
    "Accountant",
    "Insurance",
]

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "contacts.json"

MEMBER_SEARCH_URL = "https://hub.provisors.com/membersearch"

# JS to parse card-detail blocks on a results page
PARSE_CARDS_JS = """() => {
    const cards = document.querySelectorAll('ul.card-detail');
    const results = [];
    cards.forEach(card => {
        const fields = {};
        card.querySelectorAll('li').forEach(li => {
            const label = li.querySelector('label.card-detail-label');
            const value = li.querySelector('span.card-detail-value');
            if (label && value) {
                const key = label.innerText.trim();
                // For Member Info, get the link text (name)
                const link = value.querySelector('a');
                const val = link ? link.innerText.trim() : value.innerText.trim();
                fields[key] = val;
            }
        });
        if (fields['Member Info']) {
            results.push({
                name: fields['Member Info'] || '',
                profession: fields['Profession'] || '',
                focus: fields['Professional Focus'] || '',
                email: fields['Email'] || '',
                company: fields['Company'] || '',
                homeGroup: fields['Home Group'] || '',
                groups: fields['Groups'] || '',
                bio: fields['Short Bio'] || '',
                phone: fields['Account Phone'] || ''
            });
        }
    });
    // Pagination check
    const text = document.body.innerText;
    const match = text.match(/Page\\s+(\\d+)\\s+of\\s+(\\d+)/);
    const currentPage = match ? parseInt(match[1]) : 1;
    const totalPages = match ? parseInt(match[2]) : 1;
    return { members: results, currentPage, totalPages };
}"""


async def navigate_to_search_form(bot):
    """Navigate to the member search form (2-step: landing → form)."""
    await bot.page.goto(MEMBER_SEARCH_URL, wait_until="networkidle", timeout=30000)
    await bot.page.wait_for_timeout(3000)
    member_btn = bot.page.locator('input[type="submit"][value="Member Search"]')
    if await member_btn.count():
        await member_btn.click()
        await bot.page.wait_for_load_state("networkidle", timeout=30000)
        await bot.page.wait_for_timeout(3000)


async def search_by_profession(bot, profession):
    """Search by Profession dropdown, paginate through all results."""
    await navigate_to_search_form(bot)

    # Select profession
    prof_select = bot.page.locator('select').first
    if await prof_select.count():
        await prof_select.select_option(label=profession)
        await bot.page.wait_for_timeout(500)

    # Click Search
    search_btn = bot.page.locator('input[type="submit"][value="Search"]')
    if not await search_btn.count():
        search_btn = bot.page.locator('input[type="submit"]').first
    await search_btn.click()
    await bot.page.wait_for_load_state("networkidle", timeout=30000)
    await bot.page.wait_for_timeout(3000)

    # Paginate through all results
    all_members = []
    while True:
        result = await bot.page.evaluate(PARSE_CARDS_JS)
        members = result.get("members", [])
        all_members.extend(members)
        current = result.get("currentPage", 1)
        total = result.get("totalPages", 1)
        print(f"    Page {current}/{total}: {len(members)} members")

        if current >= total:
            break

        # Click Next
        next_btn = bot.page.locator("a:has-text('Next'), a[title*='Next']").first
        if not await next_btn.count():
            # Try clicking page number
            next_page = bot.page.locator(f"a:has-text('{current + 1}')").first
            if not await next_page.count():
                break
            await next_page.click()
        else:
            await next_btn.click()

        await bot.page.wait_for_load_state("networkidle", timeout=15000)
        await bot.page.wait_for_timeout(2000)

    return all_members


async def harvest():
    bot = HubBot()
    try:
        await bot.launch()
        print("Logging in...")
        success = await bot.login()
        if not success:
            print("ERROR: Login failed")
            return

        all_contacts = []
        seen = set()

        for prof in PROFESSIONS:
            print(f"\nSearching profession: '{prof}'...")
            members = await search_by_profession(bot, prof)

            added = 0
            for m in members:
                key = (m.get("name") or "").strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                groups = (m.get("groups") or "").strip().rstrip(",").strip()
                all_contacts.append({
                    "name": m["name"].strip(),
                    "company": (m.get("company") or "").strip(),
                    "profession": (m.get("profession") or "").strip(),
                    "groups": groups,
                    "notes": (m.get("email") or "").strip(),
                    "source": "hub",
                    "added": datetime.now().strftime("%Y-%m-%d")
                })
                added += 1
            print(f"  → {len(members)} total, {added} new unique (running total: {len(all_contacts)})")

        # Sort by name
        all_contacts.sort(key=lambda c: c["name"].lower())

        # Write output
        OUTPUT_DIR.mkdir(exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_contacts, f, indent=2, ensure_ascii=False)

        print(f"\nHarvested {len(all_contacts)} unique contacts → {OUTPUT_FILE}")

    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(harvest())
