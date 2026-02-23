"""
ProVisors Meet Scheduler — Local API server
Bridges the frontend (index.html) with the Hub bot (Playwright).
Run: uvicorn server:app --reload --port 3002
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from bot.hub_bot import HubBot

app = FastAPI(title="ProVisors Meet Scheduler API")

# Allow the frontend (file:// or Vercel) to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the frontend
@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")

# ── Bot singleton ──
bot: HubBot | None = None
bot_lock = asyncio.Lock()


async def get_bot() -> HubBot:
    global bot
    async with bot_lock:
        if bot is None:
            bot = HubBot()
            await bot.launch()
        return bot


@app.on_event("shutdown")
async def shutdown_bot():
    global bot
    if bot:
        await bot.close()
        bot = None


# ── API Endpoints ──

@app.post("/api/hub/login")
async def hub_login():
    """Log into the ProVisors Hub."""
    try:
        b = await get_bot()
        success = await b.login()
        return {"success": success, "message": "Logged in" if success else "Login failed — check credentials"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hub/sync")
async def hub_sync():
    """Full sync: login + scrape registrations + upcoming events."""
    try:
        b = await get_bot()
        data = await b.full_sync()

        # Cache locally
        Path("hub_sync_data.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hub/registrations")
async def hub_registrations():
    """Get current meeting registrations from the Hub."""
    try:
        b = await get_bot()
        data = await b.get_my_registrations()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hub/events")
async def hub_events():
    """Get upcoming events from the Hub."""
    try:
        b = await get_bot()
        data = await b.get_upcoming_events()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hub/snapshot")
async def hub_snapshot():
    """Get personal snapshot/dashboard data."""
    try:
        b = await get_bot()
        data = await b.get_personal_snapshot()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hub/search-events")
async def hub_search_events(q: str = ""):
    """Search all events on the Hub."""
    try:
        b = await get_bot()
        data = await b.search_events(q)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hub/my-groups")
async def hub_my_groups():
    """Get my group affiliations from the Hub."""
    try:
        b = await get_bot()
        data = await b.get_my_groups()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RegisterRequest(BaseModel):
    event_url: str


@app.post("/api/hub/register")
async def hub_register(req: RegisterRequest):
    """Register for a specific event via the Hub."""
    try:
        b = await get_bot()
        result = await b.register_for_event(req.event_url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hub/search-members")
async def hub_search_members(q: str = "", region: str = ""):
    """Search the Hub member directory by keyword."""
    try:
        b = await get_bot()
        data = await b.search_members(q, region)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hub/cached")
async def hub_cached():
    """Return the last cached sync data (no bot needed)."""
    cache = Path("hub_sync_data.json")
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    return {"error": "No cached data. Run a sync first."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3002)
