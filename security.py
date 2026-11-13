import os
import time
from collections import defaultdict, deque
from typing import Optional
from fastapi import Header, HTTPException, Request

RATE_LIMIT = 20      # 每个 IP 每分钟最多 20 次
WINDOW = 60
_hits = defaultdict(deque)


def _get_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def verify_access(x_access_code: Optional[str] = Header(default=None)):
    # 关键：每次请求时读取，不在模块导入时读
    expected = os.getenv("ACCESS_CODE", "").strip()

    print(
        "verify_access: has_code=%s, got_code=%s"
        % (bool(expected), bool(x_access_code))
    )

    if expected and x_access_code != expected:
        raise HTTPException(status_code=401, detail="invalid access code")


def rate_limit(request: Request):
    ip = _get_ip(request)
    now = time.time()
    q = _hits[ip]

    while q and now - q[0] > WINDOW:
        q.popleft()

    if len(q) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="too many requests")

    q.append(now)