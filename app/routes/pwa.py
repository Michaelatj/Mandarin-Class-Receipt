"""
routes/pwa.py - manifest, service worker and offline page so the site can be installed
on a phone. Everything here is public and static; no user data is cached.
"""
import json
from flask import Blueprint, Response, current_app, send_from_directory

pwa_bp = Blueprint("pwa", __name__)

_MANIFEST = {
    "id": "/",
    "name": "中文课堂 Mandarin Class",
    "short_name": "中文课堂",
    "description": "Attendance, tuition receipts, schedule and quizzes for Mandarin class.",
    "start_url": "/",
    "scope": "/",
    "display": "standalone",
    "orientation": "portrait",
    "background_color": "#19160f",
    "theme_color": "#19160f",
    "lang": "en",
    "icons": [
        {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "/static/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
    "shortcuts": [
        {"name": "Quiz", "url": "/quiz", "icons": [{"src": "/static/icons/icon-192.png", "sizes": "192x192"}]},
    ],
}


@pwa_bp.route("/manifest.webmanifest")
def manifest():
    resp = Response(json.dumps(_MANIFEST, ensure_ascii=False), mimetype="application/manifest+json")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


@pwa_bp.route("/sw.js")
def service_worker():
    # served from the site root so its scope covers every page
    resp = send_from_directory(current_app.static_folder, "sw.js", mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@pwa_bp.route("/offline")
def offline():
    resp = Response(_OFFLINE_HTML, mimetype="text/html")
    resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


_OFFLINE_HTML = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Offline</title>
<style>
  body { margin:0; min-height:100vh; display:grid; place-items:center; background:#19160f; color:#f0ece4;
         font-family: system-ui, sans-serif; text-align:center; padding:24px; }
  .zh { font-size:2.4rem; color:#e8c87a; margin-bottom:6px; }
  p { color:#b0a898; max-width:320px; line-height:1.55; }
  button { margin-top:14px; padding:11px 22px; border:0; border-radius:10px; background:#b07d2e; color:#fff; font-size:1rem; }
</style></head>
<body><div>
  <div class="zh">中文课堂</div>
  <h2>You are offline</h2>
  <p>This page needs a connection. Check your network and try again.</p>
  <button onclick="location.reload()">Try again</button>
</div></body></html>
"""
