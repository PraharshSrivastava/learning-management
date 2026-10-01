# Corporate email drafts and configurable TTS

These changes are on `fix/smtp-email-drafts`. They do not add HOD dashboard navigation or admin-trainer oversight.

## Configuration

Set `TTS_MODEL_NAME=Qwen/Qwen3-TTS-12Hz-1.7B-Base` only on deployments whose speech endpoint accepts this model identifier. Existing deployments without this variable retain `qwen3-tts`. Blank identifiers fail validation.

`TTS_ENDPOINT` must be reachable from the backend container. `localhost:8093` refers to the backend container itself, not the host. The model change does not change the endpoint or voice automatically. Validate the endpoint's support for the existing voice, language, temperature and WAV response parameters. LMS requests remain non-streaming.

Set `LMS_HUB_LOGIN_URL` to the real company Hub login/access URL. Employee and trainer emails use one general **Open LMS** button. If this is unset, HTML buttons are omitted and plain text directs users to the Hub dashboard. Existing role-specific public URLs are not used as deep links in these emails. Do not use the preview's example Hub URL in a deployment.

Rebuild and recreate the backend after pulling the merged change. Do not change database or storage mounts, SMTP relay/TLS configuration, allowlists or test-mode controls as part of this update.

## HOD behavior

All HOD emails are self-contained, with no report button, URL or instruction to visit a dashboard. Every digest row is included rather than truncating the report at 25 rows.

Assignment messages now use the existing digest queue, grouped by reporting manager across courses. Normal delivery is the next configured `EMAIL_DIGEST_SEND_TIME` in `EMAIL_NOTIFICATION_TIMEZONE`, with a 24-hour assignment-digest cooldown. For example, courses assigned at 14:00 are summarized at the next day's 09:00 if that is the configured digest time. Employee assignment notifications remain immediate when the worker processes them.

In test mode, assignment digests use `EMAIL_TEST_DIGEST_DELAY_MINUTES` for the first batch. Later assignments join the pending batch without extending its deadline. Subsequent batches retain the 24-hour cooldown. Existing due-soon, completion and overdue schedules are unchanged.

Pending/failed legacy HOD assignment notifications are migrated to digests by the notification cycle. Sent historical notifications are not replayed. Revoked, completed, unpublished, inactive or outdated-lifecycle assignments are checked again before sending. Missing or non-allowlisted managers do not receive digests. Employee messages are re-rendered before delivery to use current wording and progress.

## Verification

Run the email, settings and TTS regression tests before deployment. Regenerate the preview gallery using `backend/scripts/preview_email_notifications.py`; this sends no email and uses a clearly sample Hub URL.

On the deployed backend, inspect the effective TTS model and login URL without printing secrets. Test a short real speech request and verify playable WAV audio before generating a full course. Test a new assignment using approved UAT recipients: employee receives an assignment email, HOD receives one consolidated assignment digest, and HOD emails have no links. Check two different managers receive separate reports. Complete one test assignment before the reminder becomes eligible and confirm no stale reminder is sent.

This patch's mocked speech test verifies request construction, not compatibility with the actual on-prem TTS server. No external mail is sent by automated tests.
