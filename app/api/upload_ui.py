"""
Serve the built-in chat UI.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Chat UI"])
UI_INDEX_PATH = Path(__file__).resolve().parents[2] / "static" / "index.html"
NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

FALLBACK_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PublicGPT</title>
</head>
<body>
  <p>Chat UI file is missing. Please restore static/index.html.</p>
</body>
</html>
"""


@router.get("/ui", response_class=HTMLResponse)
def chat_ui():
    if UI_INDEX_PATH.exists():
        return HTMLResponse(
            UI_INDEX_PATH.read_text(encoding="utf-8"),
            headers=NO_CACHE_HEADERS,
        )
    return HTMLResponse(FALLBACK_HTML, headers=NO_CACHE_HEADERS)
