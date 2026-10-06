"""Media URLs do not grant reporting users course-content access."""

import re
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


class PrivateCourseStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        request = Request(scope)
        principal = await run_in_threadpool(media_principal, request, request.headers.get("Authorization"))
        full_path = request.url.path
        course_ids = await run_in_threadpool(asset_courses, full_path)
        await run_in_threadpool(authorize_course_media, principal, course_ids)
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        ticket = request.query_params.get("media_ticket")
        if ticket and path.endswith((".m3u8", ".html")) and response.status_code == 200:
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
