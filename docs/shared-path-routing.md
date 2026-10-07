# LMS root and shared-path deployment

Each running frontend container serves its direct root URL and its shared mount at the same time.
The employee mount is `/lms/`.
The trainer mount is `/lms/trainer/`.
No public hostname, IP address, or port is part of the frontend build.

## Proxy contract

The Hub edge preserves the full path when it sends a request to a frontend.
Each frontend strips its own mount before it sends API or generated-asset requests to the private backend.
Backend API routes remain `/api/...`.
The frontend sets `X-LMS-App` to its fixed role and replaces `X-Forwarded-Prefix` with the matched mount.
It does not accept the client's prefix.
The backend accepts only root or the fixed mount for the requested role.
A configured ASGI `root_path` takes priority over the internal prefix header.

The frontend nginx configuration is a Docker entrypoint template.
Set `TRUSTED_EDGE_PROXY_IP` to the dedicated edge container's IPv4 address.
The default is empty and trusts no forwarded scheme.
Only that exact source address can supply `X-Forwarded-Proto`.
Direct HTTP clients cannot claim HTTPS.
Do not configure `real_ip` to change the source address before this check.
Host headers retain the public port.
API proxy locations forward WebSocket upgrades and disable response buffering for streaming.

Keep the backend private to the app network.
For shared deployment, use the Hub-owned Compose network overrides and remove the backend's published port.
The backend's allowed-prefix check validates syntax and role; it does not make a publicly exposed backend trust boundary safe.
Frontend direct ports can remain published.

## Frontend runtime

Nginx changes only the base tag in entry HTML for the prefixed mount.
JavaScript build files are identical in both modes.
Flutter bootstrap resolves the entrypoint, asset directory, and local CanvasKit files from `document.baseURI`.
Missing known build files return 404 rather than entry HTML.
The `.env` asset loads under the selected mount.

Leave `API_BASE_URL` empty for same-origin root and shared operation.
Both Flutter apps centralize API mount selection in `LmsRuntimeUrls`.
An absolute API override keeps its existing meaning.
A path-relative override resolves inside the active mount.
An origin-relative override such as `/proxy` resolves at the origin root.
WebSocket URLs use the resolved API origin, scheme, port, and mount.

Generated slide HTML already uses relative stylesheet and image paths.
Video and slide URL builders use the active API mount.
Nginx serves video files with byte-range support at both mounts.
The frontend images build with PWA registration disabled.
Entry HTML unregisters only a worker whose scope matches the active mount.
It does not clear shared-origin cache storage or other apps' workers.

## Sessions and cookies

Launch endpoints exchange the Hub launch token for an independently typed LMS session token.
Session tokens cannot be used as launch tokens.
Trainer and employee cookie names remain `lms_trainer_hub` and `lms_employee_hub` by default.
Root mode uses cookie path `/`.
Shared mode uses `/lms/` or `/lms/trainer/`.
Logout deletes the same cookie name at the same path and with the same security settings.
When a browser sends both root and mount cookies with the same name, the backend uses the first cookie, which browsers send in most-specific-path order.
It does not fall back to a root cookie when the more-specific cookie is invalid.

Set `HUB_COOKIE_SECURE=false` for direct HTTP origins.
Set it to `true` when those origins use TLS.
`HUB_SHARED_COOKIE_SECURE` optionally sets a separate explicit policy for shared mounts.
Leave it empty to inherit `HUB_COOKIE_SECURE`.
For direct HTTP and a TLS edge at the same time, set root policy to `false` and shared policy to `true`.
No request scheme header controls cookie security.

Cookies do not isolate ports.
Different hostnames do isolate host-only cookies and need a new Hub launch.
Hub, LMS trainer, LMS employee, and AI have independent sessions.
There is no global logout.
Frontend access logs omit query strings and Referer headers so they do not record launch or media tokens.

## Verification

Run the backend tests with `uv` and the project's development dependencies.
Enable real Docker nginx tests with `LMS_TEST_DOCKER=1` when Docker and the pinned nginx image are available.
The tests use local fixtures, generated ports, and temporary Docker networks.

```sh
cd backend
LMS_TEST_DOCKER=1 ../.venv/bin/python -m pytest tests/test_hub_launch.py tests/test_public_mount.py tests/test_hub_websocket.py tests/test_nginx_public_mount.py
```

For each frontend, create a local `.env` containing `API_BASE_URL=` before tests.
The Docker build already creates this file.
Use the locked Flutter dependencies and run `flutter test test/lms_runtime_urls_test.dart`.

## Existing limits found during verification

The browser still requests Flutter's default Roboto fallback from `fonts.gstatic.com`.
Both HLS players still load `hls.js` from a CDN.
These are existing offline-deployment gaps, not prefix-routing requirements.
Package these resources before an air-gapped deployment.
The checked web builds use local Flutter 3.44.2; Dockerfiles still pin Flutter 3.24.5.
No Flutter version change is part of this work.
