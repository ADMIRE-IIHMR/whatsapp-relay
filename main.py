from fastapi import FastAPI, Request, Header
from fastapi.responses import Response, JSONResponse
import requests
import os
import logging

log = logging.getLogger("relay")
logging.basicConfig(level=logging.INFO)

app = FastAPI()

WHATSAPP_TOKEN  = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
RELAY_SECRET    = os.environ.get("RELAY_SECRET")

WA_BASE = f"https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}"
WA_HDR  = lambda: {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

# ─────────────────────────────────────────────
# HEALTH CHECK  ← required by whatsapp_bot.py keepalive
# ─────────────────────────────────────────────
@app.get("/health")
@app.get("/")
def home():
    return {"status": "relay alive"}

# ─────────────────────────────────────────────
# SEND MESSAGE
# ─────────────────────────────────────────────
@app.post("/relay/message")
async def relay_message(req: Request, x_relay_secret: str = Header(None)):
    if x_relay_secret != RELAY_SECRET:
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    data = await req.json()
    url  = f"{WA_BASE}/messages"

    try:
        r = requests.post(url, json=data,
                          headers={**WA_HDR(), "Content-Type": "application/json"},
                          timeout=20)
        # Return FB's status code so whatsapp_bot.py can detect errors
        return JSONResponse(r.json(), status_code=r.status_code)
    except requests.exceptions.Timeout:
        log.error("relay_message: timeout reaching graph.facebook.com")
        return JSONResponse({"error": "upstream timeout"}, status_code=504)
    except Exception as e:
        log.error("relay_message error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=502)

# ─────────────────────────────────────────────
# UPLOAD MEDIA (PDF)
# ─────────────────────────────────────────────
@app.post("/relay/media")
async def relay_media(req: Request, x_relay_secret: str = Header(None)):
    if x_relay_secret != RELAY_SECRET:
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    try:
        form = await req.form()
        file = form["file"]
        url  = f"{WA_BASE}/media"

        files = {
            "file": (file.filename, await file.read(), "application/pdf"),
            "type": (None, "application/pdf"),
            "messaging_product": (None, "whatsapp"),
        }

        r = requests.post(url, headers=WA_HDR(), files=files, timeout=60)
        return JSONResponse(r.json(), status_code=r.status_code)
    except Exception as e:
        log.error("relay_media error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=502)

# ─────────────────────────────────────────────
# DOWNLOAD MEDIA
# ─────────────────────────────────────────────
@app.get("/relay/media/{media_id}")
def relay_download(media_id: str, x_relay_secret: str = Header(None)):
    if x_relay_secret != RELAY_SECRET:
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    try:
        # Step 1: get CDN URL from Meta
        meta = requests.get(f"https://graph.facebook.com/v25.0/{media_id}",
                            headers=WA_HDR(), timeout=15).json()
        media_url = meta.get("url")
        if not media_url:
            log.error("relay_download: no url in meta: %s", meta)
            return JSONResponse({"error": "no media url", "meta": meta}, status_code=404)

        # Step 2: fetch binary
        r = requests.get(media_url, headers=WA_HDR(), timeout=60)
        return Response(content=r.content, media_type="application/octet-stream")
    except requests.exceptions.Timeout:
        log.error("relay_download: timeout for media_id=%s", media_id)
        return JSONResponse({"error": "upstream timeout"}, status_code=504)
    except Exception as e:
        log.error("relay_download error: %s", e)
        return JSONResponse({"error": str(e)}, status_code=502)
