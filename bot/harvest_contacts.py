"""
Harvest CRE contacts from ProVisors Hub member directory.
Uses hub_bot.py search_members() with the same 11 CRE keywords as the frontend.
Deduplicates by name, writes results to data/contacts.json.

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

CRE_KEYWORDS = [
    "commercial real estate", "mortgage broker", "lender", "title", "escrow",
    "appraiser", "insurance", "accountant", "attorney real estate",
    "property management", "1031 exchange"
]

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = OUTPUT_DIR / "contacts.json"


async def harvest():
    bot = HubBot()
    try:
        await bot.launch()
        print("Logging in...")
        success = await bot.login()
        if not success:
            print("ERROR: Login failed")
            return

        all_members = []
        seen = set()

        for kw in CRE_KEYWORDS:
            print(f"\nSearching: '{kw}'...")
            results = await bot.search_members(query=kw)
            for m in results:
                key = (m.get("name") or "").strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                all_members.append({
                    "name": (m.get("name") or "").strip(),
                    "company": (m.get("company") or "").strip(),
                    "profession": (m.get("profession") or "").strip(),
                    "groups": ", ".join(m.get("groups", [])) if isinstance(m.get("groups"), list) else (m.get("groups") or ""),
                    "notes": (m.get("email") or "").strip(),
                    "source": "hub",
                    "added": datetime.now().strftime("%Y-%m-%d")
                })

        # Sort by name
        all_members.sort(key=lambda c: c["name"].lower())

        # Write output
        OUTPUT_DIR.mkdir(exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_members, f, indent=2, ensure_ascii=False)

        print(f"\nHarvested {len(all_members)} unique contacts → {OUTPUT_FILE}")

    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(harvest())
