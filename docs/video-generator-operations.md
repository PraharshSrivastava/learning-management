# Video Generator operations

The LMS can make module videos itself (`VIDEO_GENERATION_MODE=local`) or send each
module to the Video Generator API (`external`). The production LMS on big-coding
(`/home/karphi/intelligence_layer`) uses `external` since 2026-10-29.

## What production needs

1. Three settings in the deployment `.env`. Never print or commit the secret.

   ```
   VIDEO_GENERATION_MODE=external
   VIDEO_SERVICE_BASE_URL=http://video-generator-isolated-api-1:8080
   VIDEO_SERVICE_HMAC_SECRET=<same value as INTEGRATION_HMAC_SECRET in the Video Generator runtime.env>
   ```

2. The backend on the Video Generator's proxy network, through the overlay
   `deploy/lms.video-generator.yml`. A copy is kept beside the other overlays in
   `/home/karphi/intelligence_layer/lms.video-generator.yml`.

The backend refuses to start in `external` mode without a base URL or with a secret
shorter than 32 characters.

## Deploying the LMS

Include the overlay in every compose command, after the existing files. Without it,
a redeploy drops the network and every module video fails with a connection error.

```bash
cd /home/karphi/intelligence_layer
docker compose -p intelligence_layer \
  -f docker-compose.yml \
  -f lms.pr-onprem.yml \
  -f lms.edge-network.yml \
  -f lms.document-builder.images.yml \
  -f lms.video-generator.yml \
  up -d --wait backend
```

Restarting only the backend is enough for a settings change (`--no-deps`). Check that
no course is generating first: a restart interrupts running generation jobs.

## Checks

```bash
docker exec intelligence_layer-backend-1 printenv VIDEO_GENERATION_MODE VIDEO_SERVICE_BASE_URL
docker inspect intelligence_layer-backend-1 --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
```

The networks must include `video-generator-proxy`. A signed status request for an
unknown run ID returning `404 Animation request not found` confirms the address and
secret; `401` means the secret does not match.

| Symptom | Cause |
|---|---|
| Module video fails with a connection error | Backend not on `video-generator-proxy`, or the Video Generator API is down |
| `401` from the Video Generator | `VIDEO_SERVICE_HMAC_SECRET` differs from its `INTEGRATION_HMAC_SECRET` |
| Backend does not start after the change | Missing base URL or a secret shorter than 32 characters |

## Switching back

Set `VIDEO_GENERATION_MODE=local` (or restore the dated `.env` backup) and restart the
backend. Stored module videos stay attached either way; only new or regenerated
modules use the selected mode.

## Video Generator side

The Video Generator's LMS settings (`INTEGRATION_*`: voice, logo, options) live in
its release folder's `infra/onprem/runtime.env` and must be carried to each new
release folder. LMS requests get its LMS artwork defaults automatically.
