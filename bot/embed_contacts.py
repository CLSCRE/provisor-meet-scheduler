"""
Embed harvested contacts into index.html as EMBEDDED_CONTACTS array.
Reads data/contacts.json and writes/updates the constant in index.html.

Run after harvest_contacts.py:
  python bot/embed_contacts.py
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import json
import re
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "contacts.json"
INDEX_FILE = Path(__file__).resolve().parent.parent / "index.html"

# Markers in index.html that bracket the embedded contacts array
START_MARKER = "// ── Embedded Contacts (auto-generated) ──"
END_MARKER = "// ── End Embedded Contacts ──"


def build_js_array(contacts):
    """Convert contacts list to a compact JS array literal."""
    lines = []
    for c in contacts:
        # Escape single quotes in values
        def esc(s):
            return (s or "").replace("\\", "\\\\").replace("'", "\\'")
        lines.append(
            f"  {{name:'{esc(c['name'])}',company:'{esc(c['company'])}',profession:'{esc(c['profession'])}',groups:'{esc(c['groups'])}',notes:'{esc(c['notes'])}',source:'hub',added:'{esc(c['added'])}'}}"
        )
    return "const EMBEDDED_CONTACTS = [\n" + ",\n".join(lines) + "\n];"


def embed():
    if not DATA_FILE.exists():
        print(f"ERROR: {DATA_FILE} not found. Run harvest_contacts.py first.")
        sys.exit(1)

    contacts = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    print(f"Loaded {len(contacts)} contacts from {DATA_FILE}")

    html = INDEX_FILE.read_text(encoding="utf-8")

    js_block = f"{START_MARKER}\n{build_js_array(contacts)}\n{END_MARKER}"

    if START_MARKER in html and END_MARKER in html:
        # Replace existing block
        pattern = re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER)
        html = re.sub(pattern, js_block, html, flags=re.DOTALL)
        print("Replaced existing EMBEDDED_CONTACTS block.")
    else:
        # Insert before "// ── Groups Data ──"
        anchor = "// ── Groups Data ──"
        if anchor not in html:
            print(f"ERROR: Could not find anchor '{anchor}' in index.html")
            sys.exit(1)
        html = html.replace(anchor, js_block + "\n\n" + anchor)
        print("Inserted new EMBEDDED_CONTACTS block before Groups Data.")

    INDEX_FILE.write_text(html, encoding="utf-8")
    print(f"Embedded {len(contacts)} contacts into {INDEX_FILE}")


if __name__ == "__main__":
    embed()
