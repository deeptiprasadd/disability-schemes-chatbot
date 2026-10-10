"""
Protection for a public deployment.

Every answer spends the shared Groq quota, so one visitor (or a bot) must not
be able to use it all up, and oversized inputs must not exhaust memory or the
LLM's context. Limits are per visitor IP, kept in memory (one server process).
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import Request

MAX_MESSAGE_CHARS = 2000
MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CHARS = 4000          # per past message
MAX_DOC_CHARS = 20000             # uploaded-document text sent with a question
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_AUDIO_BYTES = 10 * 1024 * 1024

# bucket -> (requests allowed, per this many seconds), per visitor
LIMITS = {
    "chat": (20, 600),
    "voice": (20, 600),
    "tts": (40, 600),
    "upload": (10, 600),
    "extras": (60, 600),   # follow-up chips + matches panel: two per answer
}

TOO_MANY = "You've sent a lot of requests in a short time. Wait a few minutes, then try again."

_hits: dict = defaultdict(deque)
_lock = threading.Lock()


def client_id(request: Request) -> str:
    """The visitor's IP. Behind a host's proxy the real one is in X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def allow(bucket: str, request: Request) -> bool:
    """Record one request; False if this visitor is over the bucket's limit."""
    limit, window = LIMITS[bucket]
    key = (bucket, client_id(request))
    now = time.monotonic()
    with _lock:
        if len(_hits) > 50_000:          # bound memory under a flood of distinct IPs
            _hits.clear()
        q = _hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True
