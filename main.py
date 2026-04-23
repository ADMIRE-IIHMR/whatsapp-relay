from fastapi import FastAPI, Request, Header
import requests
import os

app = FastAPI()

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
RELAY_SECRET = os.environ.get("RELAY_SECRET")

@app.get("/")
def home():
    return {"status": "relay alive"}

@app.post("/relay/message")
async def relay_message(req: Request, x_relay_secret: str = Header(None)):
    if x_relay_secret != RELAY_SECRET:
        return {"error": "unauthorized"}

    data = await req.json()

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        r = requests.post(url, json=data, headers=headers, timeout=30)
        return {"status": r.status_code, "response": r.text}
    except Exception as e:
        return {"error": str(e)}

@app.post("/relay/media")
async def relay_media(req: Request, x_relay_secret: str = Header(None)):
    if x_relay_secret != RELAY_SECRET:
        return {"error": "unauthorized"}

    form = await req.form()
    file = form["file"]

    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/media"

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}"
    }

    files = {
        "file": (file.filename, await file.read(), "application/pdf"),
        "type": (None, "application/pdf"),
        "messaging_product": (None, "whatsapp")
    }

    r = requests.post(url, headers=headers, files=files)
    return r.json()

@app.get("/relay/media/{media_id}")
def relay_download(media_id: str, x_relay_secret: str = Header(None)):
    if x_relay_secret != RELAY_SECRET:
        return {"error": "unauthorized"}

    meta_url = f"https://graph.facebook.com/v18.0/{media_id}"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

    meta = requests.get(meta_url, headers=headers).json()
    media_url = meta.get("url")

    if not media_url:
        return {"error": "no media url"}

    data = requests.get(media_url, headers=headers)
    return data.content
