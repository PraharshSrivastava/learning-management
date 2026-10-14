"""Media URLs do not grant reporting users course-content access."""

import re
import stat
from urllib.parse import quote

from fastapi import APIRouter, Header, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app.security.hub_launch import HubApp
from app.services.media_access import (
    asset_courses,
    authorize_course_media,
    issue_media_ticket,
    media_principal,
)

router = APIRouter(prefix="/api", tags=["media"])


@router.get("/media-ticket")
def media_ticket(request: Request, app: HubApp, authorization: str | None = Header(default=None)):
    return Response(content='{"ticket":"' + issue_media_ticket(request, authorization, app) + '"}',
                    media_type="application/json", headers={"Cache-Control": "no-store"})


# Sent by the frontend nginx only. It overwrites any client value, so a browser
# cannot ask for an internal redirect.
ACCEL_HEADER = "x-lms-accel-videos"

class PrivateCourseStaticFiles(StaticFiles):
    def __init__(self, *args, accel_location: str | None = None, **kwargs):
        """accel_location is the nginx `internal` location that maps to this directory."""
        super().__init__(*args, **kwargs)
        self.accel_location = accel_location

    async def get_response(self, path, scope):
        request = Request(scope)
        principal = await run_in_threadpool(media_principal, request, request.headers.get("Authorization"))
        full_path = request.url.path
        course_ids = await run_in_threadpool(asset_courses, full_path)
        await run_in_threadpool(authorize_course_media, principal, course_ids)
        ticket = request.query_params.get("media_ticket")
        rewrites_playlist = bool(ticket) and path.endswith((".m3u8", ".html"))
        if self.accel_location and request.headers.get(ACCEL_HEADER) == "1" and not rewrites_playlist:
            # Authorization passed. Let nginx send the bytes with Range support.
            full_file, stat_result = await run_in_threadpool(self.lookup_path, path)
            if stat_result is not None and stat.S_ISREG(stat_result.st_mode):
                return Response(status_code=200, headers={
                    "X-Accel-Redirect": self.accel_location + quote(path.lstrip("/")),
                    "Cache-Control": "no-store",
                    "Referrer-Policy": "no-referrer",
                })
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        if rewrites_playlist and response.status_code == 200:
            from pathlib import Path
            file_path, _ = await run_in_threadpool(self.lookup_path, path)
            content = await run_in_threadpool(Path(file_path).read_text, encoding="utf-8")
            suffix = "media_ticket=" + quote(ticket, safe="")

            def protected(url):
                if url.startswith(("http:", "https:", "data:", "file:")):
                    return url
                return url + ("&" if "?" in url else "?") + suffix

            if path.endswith(".m3u8"):
                content = "\n".join(protected(line) if line and not line.startswith("#") else
                    re.sub(r'URI="([^"]+)"', lambda m: 'URI="' + protected(m[1]) + '"', line)
                    for line in content.splitlines())
            else:
                content = re.sub(r'(src|href)="([^"]+)"', lambda m: m[1] + '="' + protected(m[2]) + '"', content)
            return Response(content, media_type="application/vnd.apple.mpegurl" if path.endswith(".m3u8") else "text/html",
                            headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        return response
