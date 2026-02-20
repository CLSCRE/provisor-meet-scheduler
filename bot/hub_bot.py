"""
ProVisors Hub Bot — Playwright automation for hub.provisors.com
Handles login, scraping registered meetings, and booking new ones.
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

HUB_BASE = "https://hub.provisors.com"
LOGIN_URL = f"{HUB_BASE}/NC__Login"
MY_REGISTRATIONS_URL = f"{HUB_BASE}/nc__myregistrations"
UPCOMING_EVENTS_URL = f"{HUB_BASE}/upcoming-events"
EVENT_SEARCH_URL = f"{HUB_BASE}/event-search"
MY_GROUPS_URL = f"{HUB_BASE}/myaffiliations"
PERSONAL_SNAPSHOT_URL = f"{HUB_BASE}/personalsnapshot"

SCREENSHOT_DIR = Path(os.getenv("SCREENSHOT_DIR", "screenshots"))
SCREENSHOT_DIR.mkdir(exist_ok=True)


class HubBot:
    def __init__(self):
        self.email = os.getenv("PROVISORS_EMAIL", "")
        self.password = os.getenv("PROVISORS_PASSWORD", "")
        self.headless = os.getenv("HEADLESS", "true").lower() == "true"
        self.slow_mo = int(os.getenv("SLOW_MO", "0"))
        self.browser = None
        self.context = None
        self.page = None
        self.logged_in = False

    async def launch(self):
        """Launch browser with persistent profile for session reuse."""
        from patchright.async_api import async_playwright
        self.pw = await async_playwright().start()
        profile_dir = Path(".browser-profile")
        profile_dir.mkdir(exist_ok=True)
        self.context = await self.pw.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=self.headless,
            slow_mo=self.slow_mo,
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

    async def close(self):
        if self.context:
            await self.context.close()
        if self.pw:
            await self.pw.stop()

    async def screenshot(self, name="debug"):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = SCREENSHOT_DIR / f"{name}_{ts}.png"
        await self.page.screenshot(path=str(path), full_page=True)
        return str(path)

    # ── Authentication ──

    async def login(self):
        """Log into the ProVisors Hub. Returns True on success."""
        if not self.email or not self.password:
            raise ValueError("PROVISORS_EMAIL and PROVISORS_PASSWORD must be set in .env")

        await self.page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
        await self.page.wait_for_timeout(2000)

        # Check if already logged in (redirected away from login page)
        if "/NC__Login" not in self.page.url:
            self.logged_in = True
            return True

        # Fill email
        email_input = self.page.locator("input[type='email'], input[name*='email'], input[id*='email']").first
        if not await email_input.count():
            # Salesforce VF form — find by placeholder or surrounding label
            email_input = self.page.locator("input.loginInput").first
        await email_input.fill(self.email)

        # Fill password
        pwd_input = self.page.locator("input[type='password']").first
        await pwd_input.fill(self.password)

        # Click login button
        login_btn = self.page.locator("input[type='submit'][value*='Log'], button:has-text('Log In'), input.loginButton").first
        await login_btn.click()

        # Wait for navigation
        await self.page.wait_for_load_state("networkidle", timeout=30000)
        await self.page.wait_for_timeout(3000)

        # Check success — should no longer be on login page
        if "/NC__Login" in self.page.url:
            await self.screenshot("login_failed")
            self.logged_in = False
            return False

        self.logged_in = True
        await self.screenshot("login_success")
        return True

    async def ensure_logged_in(self):
        if not self.logged_in:
            success = await self.login()
            if not success:
                raise RuntimeError("Failed to log into ProVisors Hub")

    # ── Scrape My Registrations ──

    async def get_my_registrations(self):
        """
        Navigate to My Registrations and scrape all registered meetings.
        Returns list of dicts with event details.
        """
        await self.ensure_logged_in()
        await self.page.goto(MY_REGISTRATIONS_URL, wait_until="networkidle", timeout=30000)
        await self.page.wait_for_timeout(3000)
        await self.screenshot("my_registrations")

        registrations = await self.page.evaluate("""() => {
            const results = [];
            // Broad selector: grab any container with event/registration content
            const containers = document.querySelectorAll(
                '[class*="registration"], [class*="Registration"], [class*="event"], ' +
                '[class*="Event"], [class*="card"], [class*="Card"], ' +
                'table tbody tr, .slds-card, .slds-tile, ' +
                '[class*="list-item"], [class*="ListItem"], [class*="row"]'
            );
            containers.forEach(el => {
                const text = (el.innerText || el.textContent || '').trim();
                if (text.length > 20 && text.length < 2000) {
                    const links = [];
                    el.querySelectorAll('a[href]').forEach(a => {
                        links.push({ text: a.innerText.trim(), href: a.href });
                    });
                    results.push({ text: text.substring(0, 800), links });
                }
            });

            // All links on page
            const allLinks = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const t = a.innerText.trim();
                if (t.length > 2) allLinks.push({ text: t.substring(0, 200), href: a.href });
            });

            const pageText = document.body.innerText.substring(0, 8000);
            return { cards: results, links: allLinks, pageText };
        }""")

        return registrations

    # ── Scrape Upcoming Events ──

    async def get_upcoming_events(self):
        """
        Navigate to Upcoming Events and scrape all available meetings.
        Returns list of event objects.
        """
        await self.ensure_logged_in()
        await self.page.goto(UPCOMING_EVENTS_URL, wait_until="networkidle", timeout=30000)
        await self.page.wait_for_timeout(5000)  # extra time for dynamic content
        await self.screenshot("upcoming_events")

        events = await self.page.evaluate("""() => {
            const results = [];
            // Broad selector for any event-like containers
            const containers = document.querySelectorAll(
                '[class*="event"], [class*="Event"], [class*="card"], [class*="Card"], ' +
                '[class*="tile"], [class*="Tile"], [class*="list-item"], [class*="ListItem"], ' +
                'table tbody tr, .slds-card, .slds-tile, article, ' +
                '[class*="upcoming"], [class*="Upcoming"], [class*="row"]'
            );
            containers.forEach(el => {
                const text = (el.innerText || el.textContent || '').trim();
                if (text.length > 20 && text.length < 2000) {
                    const links = [];
                    el.querySelectorAll('a[href]').forEach(a => {
                        links.push({ text: a.innerText.trim(), href: a.href });
                    });
                    results.push({
                        text: text.substring(0, 800),
                        links,
                        html: el.innerHTML.substring(0, 500),
                    });
                }
            });

            // All links on page
            const allLinks = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const t = a.innerText.trim();
                if (t.length > 2) allLinks.push({ text: t.substring(0, 200), href: a.href });
            });

            const pageText = document.body.innerText.substring(0, 10000);
            return { events: results, links: allLinks, pageText };
        }""")

        return events

    # ── Search All Events ──

    async def search_events(self, search_term=""):
        """
        Navigate to the Event Search page and scrape events.
        Optionally enter a search term.
        """
        await self.ensure_logged_in()
        await self.page.goto(EVENT_SEARCH_URL, wait_until="networkidle", timeout=30000)
        await self.page.wait_for_timeout(3000)

        # If there's a search input, fill it
        if search_term:
            search_input = self.page.locator(
                'input[type="search"], input[type="text"][placeholder*="search" i], '
                'input[name*="search" i], input[class*="search" i]'
            ).first
            if await search_input.count():
                await search_input.fill(search_term)
                await search_input.press("Enter")
                await self.page.wait_for_timeout(3000)

        await self.screenshot("event_search")

        events = await self.page.evaluate("""() => {
            const results = [];
            // Grab all containers that look like event listings
            const containers = document.querySelectorAll(
                '[class*="event"], [class*="Event"], [class*="card"], [class*="Card"], ' +
                '[class*="tile"], [class*="Tile"], [class*="list-item"], [class*="ListItem"], ' +
                'table tbody tr, .slds-card, .slds-tile, article, ' +
                '[class*="result"], [class*="Result"]'
            );
            containers.forEach(el => {
                const text = (el.innerText || el.textContent || '').trim();
                if (text.length > 20 && text.length < 2000) {
                    const links = [];
                    el.querySelectorAll('a[href]').forEach(a => {
                        links.push({ text: a.innerText.trim(), href: a.href });
                    });
                    results.push({
                        text: text.substring(0, 800),
                        links,
                    });
                }
            });

            const allLinks = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const t = a.innerText.trim();
                if (t.length > 2) allLinks.push({ text: t.substring(0, 200), href: a.href });
            });

            const pageText = document.body.innerText.substring(0, 10000);
            return { events: results, links: allLinks, pageText };
        }""")

        return events

    # ── My Groups / Affiliations ──

    async def get_my_groups(self):
        """Scrape the My Groups page to see group affiliations."""
        await self.ensure_logged_in()
        await self.page.goto(MY_GROUPS_URL, wait_until="networkidle", timeout=30000)
        await self.page.wait_for_timeout(3000)
        await self.screenshot("my_groups")

        data = await self.page.evaluate("""() => {
            const results = [];
            const containers = document.querySelectorAll(
                '[class*="group"], [class*="Group"], [class*="affiliation"], ' +
                '[class*="card"], [class*="Card"], [class*="tile"], [class*="Tile"], ' +
                'table tbody tr, .slds-card, .slds-tile, article'
            );
            containers.forEach(el => {
                const text = (el.innerText || el.textContent || '').trim();
                if (text.length > 10 && text.length < 2000) {
                    const links = [];
                    el.querySelectorAll('a[href]').forEach(a => {
                        links.push({ text: a.innerText.trim(), href: a.href });
                    });
                    results.push({ text: text.substring(0, 800), links });
                }
            });

            const allLinks = [];
            document.querySelectorAll('a[href]').forEach(a => {
                const t = a.innerText.trim();
                if (t.length > 2) allLinks.push({ text: t.substring(0, 200), href: a.href });
            });

            const pageText = document.body.innerText.substring(0, 8000);
            return { groups: results, links: allLinks, pageText };
        }""")

        return data

    # ── Scrape Personal Snapshot ──

    async def get_personal_snapshot(self):
        """Scrape the personal snapshot/dashboard page for meeting info."""
        await self.ensure_logged_in()
        await self.page.goto(PERSONAL_SNAPSHOT_URL, wait_until="networkidle", timeout=30000)
        await self.page.wait_for_timeout(3000)
        await self.screenshot("personal_snapshot")

        data = await self.page.evaluate("""() => {
            const pageText = document.body.innerText.substring(0, 10000);
            const links = [];
            document.querySelectorAll('a').forEach(a => {
                if (a.href && a.innerText.trim()) {
                    links.push({ text: a.innerText.trim().substring(0, 200), href: a.href });
                }
            });
            return { pageText, links };
        }""")

        return data

    # ── Register for a Meeting ──

    async def register_for_event(self, event_url):
        """
        Navigate to an event registration page and complete registration.
        Returns dict with success status and details.
        """
        await self.ensure_logged_in()
        await self.page.goto(event_url, wait_until="networkidle", timeout=30000)
        await self.page.wait_for_timeout(3000)
        await self.screenshot("event_page")

        # Look for a Register button
        register_btn = self.page.locator(
            'button:has-text("Register"), a:has-text("Register"), '
            'input[value*="Register"], [class*="register"] button, '
            'a[href*="register"], button:has-text("RSVP"), a:has-text("RSVP")'
        ).first

        if not await register_btn.count():
            await self.screenshot("no_register_button")
            return {"success": False, "error": "No Register/RSVP button found on page"}

        await register_btn.click()
        await self.page.wait_for_load_state("networkidle", timeout=30000)
        await self.page.wait_for_timeout(3000)
        await self.screenshot("after_register_click")

        # Check for confirmation or next steps
        page_text = await self.page.evaluate("() => document.body.innerText.substring(0, 3000)")

        # Look for confirmation indicators
        confirmed = any(word in page_text.lower() for word in [
            "confirmed", "registered", "registration complete", "success",
            "thank you", "you are registered"
        ])

        # If there's a checkout/confirm step, try to complete it
        if not confirmed:
            confirm_btn = self.page.locator(
                'button:has-text("Confirm"), button:has-text("Submit"), '
                'button:has-text("Complete"), input[value*="Confirm"], '
                'button:has-text("Checkout"), a:has-text("Confirm")'
            ).first
            if await confirm_btn.count():
                await confirm_btn.click()
                await self.page.wait_for_load_state("networkidle", timeout=30000)
                await self.page.wait_for_timeout(3000)
                await self.screenshot("after_confirm")
                page_text = await self.page.evaluate("() => document.body.innerText.substring(0, 3000)")
                confirmed = any(word in page_text.lower() for word in [
                    "confirmed", "registered", "registration complete", "success", "thank you"
                ])

        return {
            "success": confirmed,
            "page_text": page_text[:500],
            "url": self.page.url,
        }

    # ── Full Sync ──

    async def full_sync(self):
        """
        Run a complete sync: login, scrape registrations, scrape events.
        Returns combined data for the frontend.
        """
        await self.ensure_logged_in()

        snapshot = await self.get_personal_snapshot()
        registrations = await self.get_my_registrations()
        events = await self.get_upcoming_events()
        event_search = await self.search_events()
        groups = await self.get_my_groups()

        return {
            "logged_in": True,
            "timestamp": datetime.now().isoformat(),
            "snapshot": snapshot,
            "registrations": registrations,
            "upcoming_events": events,
            "event_search": event_search,
            "my_groups": groups,
        }


# ── CLI entry point for testing ──
async def main():
    bot = HubBot()
    try:
        await bot.launch()
        print("Logging in...")
        success = await bot.login()
        print(f"Login: {'success' if success else 'FAILED'}")

        if success:
            print("\n" + "="*60)
            print("PERSONAL SNAPSHOT")
            print("="*60)
            snapshot = await bot.get_personal_snapshot()
            print(f"Page text (first 300 chars):\n{snapshot['pageText'][:300]}")

            print("\n" + "="*60)
            print("MY REGISTRATIONS")
            print("="*60)
            regs = await bot.get_my_registrations()
            print(f"Cards found: {len(regs.get('cards', []))}")
            print(f"Links found: {len(regs.get('links', []))}")
            print(f"Page text (first 500 chars):\n{regs['pageText'][:500]}")
            for link in regs.get('links', [])[:15]:
                print(f"  {link['text'][:60]} → {link['href']}")

            print("\n" + "="*60)
            print("UPCOMING EVENTS")
            print("="*60)
            events = await bot.get_upcoming_events()
            print(f"Event cards found: {len(events.get('events', []))}")
            print(f"Links found: {len(events.get('links', []))}")
            print(f"Page text (first 500 chars):\n{events['pageText'][:500]}")
            for link in events.get('links', [])[:15]:
                print(f"  {link['text'][:60]} → {link['href']}")

            print("\n" + "="*60)
            print("EVENT SEARCH")
            print("="*60)
            search = await bot.search_events()
            print(f"Event cards found: {len(search.get('events', []))}")
            print(f"Links found: {len(search.get('links', []))}")
            print(f"Page text (first 800 chars):\n{search['pageText'][:800]}")
            for link in search.get('links', [])[:20]:
                print(f"  {link['text'][:60]} → {link['href']}")

            print("\n" + "="*60)
            print("MY GROUPS")
            print("="*60)
            groups = await bot.get_my_groups()
            print(f"Group cards found: {len(groups.get('groups', []))}")
            print(f"Links found: {len(groups.get('links', []))}")
            print(f"Page text (first 500 chars):\n{groups['pageText'][:500]}")

            # Save full data
            data = {
                "snapshot": snapshot,
                "registrations": regs,
                "upcoming_events": events,
                "event_search": search,
                "my_groups": groups,
            }
            with open("hub_sync_data.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("\nFull data saved to hub_sync_data.json")
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
