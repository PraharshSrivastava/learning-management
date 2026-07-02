# Hub App Integration Guide

> This document describes how to integrate your application with the **PhillipCapital Hub App** so that users can launch it from the Hub dashboard with single sign-on.

---

## How It Works

```
User clicks "Launch" on Hub dashboard
        │
        ▼
Hub creates HMAC-signed token containing { app_key, email, sub, exp }
        │
        ▼
Hub redirects browser to:  YOUR_APP_URL?hub_launch_token=<TOKEN>
        │
        ▼
Your app's middleware verifies the token signature
        │
        ▼
Sets httponly cookie, redirects to clean URL
        │
        ▼
All subsequent requests: middleware reads cookie → sets request.state.hub_user
```

---

## Step 1: Environment Variables

Add these to your `docker-compose.yml` or `.env`:

```yaml
environment:
  # REQUIRED — must match Hub's APP_LAUNCH_SECRET exactly
  - HUB_LAUNCH_SECRET=hd5hqSxFfVyf/ZN5M/6mBSpwCg7isJUeUu/Mt9Fwa/g=

  # REQUIRED — your app's unique key (registered in Hub, lowercase with hyphens)
  - HUB_LAUNCH_APP_KEY=your-app-key

  # OPTIONAL — cookie name (default: your_app_launch). Use a unique name per app.
  - HUB_LAUNCH_COOKIE_NAME=your_app_launch

  # OPTIONAL — session duration in seconds (default: 28800 = 8 hours)
  - HUB_LAUNCH_SESSION_SECONDS=28800
```

---

## Step 2: Implement the Auth Middleware

Copy this middleware into your application. It handles the entire auth flow.

### Python / FastAPI (Starlette)

```python
import base64
import hashlib
import hmac
import json
import os
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse


class HubLaunchMiddleware(BaseHTTPMiddleware):
    """Verify Hub-issued launch tokens and manage session cookies."""

    def __init__(self, app):
        super().__init__(app)
        self.secret = os.getenv("HUB_LAUNCH_SECRET", "")
        self.cookie_name = os.getenv("HUB_LAUNCH_COOKIE_NAME", "app_launch")
        self.app_key = os.getenv("HUB_LAUNCH_APP_KEY", "")
        self.session_seconds = int(os.getenv("HUB_LAUNCH_SESSION_SECONDS", "28800"))
        # Paths that bypass auth (static assets, health checks)
        self.public_paths = {"/favicon.ico", "/favicon.png", "/manifest.json", "/health"}

    # ── Token helpers ──────────────────────────────────────────────

    def _b64decode(self, value: str) -> bytes:
        value += "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value.encode("ascii"))

    def _decode_valid_token(self, token: str) -> dict | None:
        if not self.secret or "." not in token:
            return None
        payload_b64, sig_b64 = token.rsplit(".", 1)
        expected = hmac.new(
            self.secret.encode("utf-8"),
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).digest()
        try:
            actual = self._b64decode(sig_b64)
            payload = json.loads(self._b64decode(payload_b64))
        except Exception:
            return None
        if not hmac.compare_digest(actual, expected):
            return None
        if payload.get("app_key") != self.app_key:
            return None
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload

    # ── Middleware dispatch ─────────────────────────────────────────

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        if not self.secret:                    # dev mode: no secret = no auth
            return await call_next(request)
        if request.url.path in self.public_paths or \
           request.url.path.startswith(("/assets/", "/static/", "/canvaskit/")):
            return await call_next(request)

        # First visit: token in query string
        launch_token = request.query_params.get("hub_launch_token")
        if launch_token:
            payload = self._decode_valid_token(launch_token)
            if payload:
                resp = RedirectResponse(str(request.url.replace(query="")), 302)
                resp.set_cookie(
                    self.cookie_name, launch_token,
                    max_age=self.session_seconds,
                    httponly=True, samesite="lax",
                )
                return resp

        # Subsequent visits: token in cookie
        cookie_token = request.cookies.get(self.cookie_name)
        if cookie_token:
            payload = self._decode_valid_token(cookie_token)
            if payload:
                request.state.hub_user = payload   # ← available in all endpoints
                return await call_next(request)

        return JSONResponse(
            {"detail": "Open this application from the Hub dashboard."},
            status_code=403,
        )
```

Register it in your app:

```python
from fastapi import FastAPI
app = FastAPI()
app.add_middleware(HubLaunchMiddleware)
```

### Node.js / Express

```javascript
const crypto = require("crypto");

const SECRET = process.env.HUB_LAUNCH_SECRET || "";
const APP_KEY = process.env.HUB_LAUNCH_APP_KEY || "";
const COOKIE = process.env.HUB_LAUNCH_COOKIE_NAME || "app_launch";
const TTL = parseInt(process.env.HUB_LAUNCH_SESSION_SECONDS || "28800");

function b64decode(str) {
  return Buffer.from(str + "=".repeat((4 - (str.length % 4)) % 4), "base64url");
}

function verifyToken(token) {
  if (!SECRET || !token || !token.includes(".")) return null;
  const [payloadB64, sigB64] = [
    token.substring(0, token.lastIndexOf(".")),
    token.substring(token.lastIndexOf(".") + 1),
  ];
  const expected = crypto
    .createHmac("sha256", SECRET)
    .update(payloadB64, "ascii")
    .digest();
  const actual = b64decode(sigB64);
  if (!crypto.timingSafeEqual(actual, expected)) return null;
  try {
    const payload = JSON.parse(b64decode(payloadB64).toString("utf8"));
    if (payload.app_key !== APP_KEY) return null;
    if (payload.exp < Math.floor(Date.now() / 1000)) return null;
    return payload;
  } catch {
    return null;
  }
}

function hubAuthMiddleware(req, res, next) {
  // Skip static assets
  if (["/favicon.ico", "/health"].includes(req.path)) return next();
  if (!SECRET) return next(); // dev mode

  // First visit: token in query string
  const launchToken = req.query.hub_launch_token;
  if (launchToken) {
    const payload = verifyToken(launchToken);
    if (payload) {
      const cleanUrl = req.originalUrl.split("?")[0];
      res.cookie(COOKIE, launchToken, {
        maxAge: TTL * 1000,
        httpOnly: true,
        sameSite: "lax",
      });
      return res.redirect(302, cleanUrl);
    }
  }

  // Subsequent visits: token in cookie
  const cookieToken = req.cookies?.[COOKIE];
  if (cookieToken) {
    const payload = verifyToken(cookieToken);
    if (payload) {
      req.hubUser = payload; // ← available in all route handlers
      return next();
    }
  }

  res.status(403).json({ detail: "Open this application from the Hub dashboard." });
}

// Usage:
// app.use(require("cookie-parser")());
// app.use(hubAuthMiddleware);
```

---

## Step 3: Access User Identity

After the middleware runs, the authenticated user's info is available on every request.

### Token Payload Structure

```json
{
  "app_key": "your-app-key",
  "app_id": 3,
  "sub": 5,
  "email": "user@phillipcapital.in",
  "exp": 1749547200
}
```

| Field     | Type   | Description                              |
|-----------|--------|------------------------------------------|
| `app_key` | string | Your application's registered key        |
| `app_id`  | int    | Application ID in Hub database           |
| `sub`     | int    | User ID in Hub database                  |
| `email`   | string | User's email — **use this for tenancy**  |
| `exp`     | int    | Token expiry (Unix timestamp)            |

### Python

```python
def _get_user_email(request: Request) -> str:
    hub_user = getattr(request.state, "hub_user", None)
    if hub_user and isinstance(hub_user, dict):
        return hub_user.get("email", "anonymous")
    return "anonymous"

@app.get("/api/my-data")
async def get_my_data(request: Request):
    email = _get_user_email(request)
    # Scope queries by email for multi-tenancy
    return db.query(MyModel).filter(MyModel.owner == email).all()
```

### Node.js

```javascript
app.get("/api/my-data", (req, res) => {
  const email = req.hubUser?.email || "anonymous";
  // Scope queries by email for multi-tenancy
  const data = db.find({ owner: email });
  res.json(data);
});
```

---

## Step 4: Multi-Tenancy (Important)

If your app stores per-user data, you **must** scope all data access by `email`:

```
✅  SELECT * FROM sessions WHERE owner = 'user@phillipcapital.in'
❌  SELECT * FROM sessions   -- leaks data across users
```

### Frontend Caching Warning

Browser `localStorage` is shared across all users on the same domain. If you cache data client-side:

- **Option A**: Key localStorage by user email: `localStorage.setItem(`data_${email}`, ...)`
- **Option B**: Only use server-returned data; don't persist in localStorage
- **Option C**: Clear localStorage when the server reports a different user

---

## Step 5: Register in Hub

Ask your Hub **Owner** to run these steps:

### 1. Create the application record

```bash
curl -X POST http://35.207.228.184/api/v1/applications \
  -H "Authorization: Bearer <OWNER_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "app_key": "your-app-key",
    "name": "Your App Name",
    "description": "What your app does",
    "url": "http://34.172.58.183:80",
    "status": "ACTIVE"
  }'
```

> The `app_key` here must **exactly match** your `HUB_LAUNCH_APP_KEY` env var.

### 2. Grant access to users or roles

```bash
# Grant to a specific user
curl -X POST http://35.207.228.184/api/v1/access/users/{user_id}/apps/{app_id} \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"access_level": "STANDARD"}'

# Grant to an entire role
curl -X POST http://35.207.228.184/api/v1/access/roles/{role_id}/apps/{app_id} \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"access_level": "STANDARD"}'
```

---

## Quick Checklist

- [ ] Set `HUB_LAUNCH_SECRET` (must match Hub's `APP_LAUNCH_SECRET`)
- [ ] Set `HUB_LAUNCH_APP_KEY` (must match the registered `app_key`)
- [ ] Set unique `HUB_LAUNCH_COOKIE_NAME` for your app
- [ ] Copy and register the `HubLaunchMiddleware`
- [ ] Access user via `request.state.hub_user` (Python) or `req.hubUser` (Node)
- [ ] Scope all data queries by `hub_user.email` for multi-tenancy
- [ ] Handle frontend caching (localStorage is shared across users)
- [ ] Ask Hub Owner to register the app and grant access
- [ ] Test: Hub dashboard → Launch → App loads → User identity works

---

## Security Notes

| Concern              | How it's handled                                                    |
|----------------------|---------------------------------------------------------------------|
| Token forgery        | HMAC-SHA256 signature verified against shared secret                |
| Token replay         | Tokens expire (default 24h); cookie expires (default 8h)            |
| Cookie theft         | `httponly=True` (no JS access), `samesite=lax`                      |
| Wrong app            | Middleware rejects tokens where `app_key` doesn't match             |
| Direct URL access    | Returns 403 if no valid cookie or token                             |
| Data leakage         | Backend must scope queries by `hub_user.email`                      |
| Secret rotation      | Update `APP_LAUNCH_SECRET` on Hub + `HUB_LAUNCH_SECRET` on all apps |
