"""Resolve fixed dates without changing legacy relative-deadline storage."""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.exceptions import DomainValidationError

ZONE = ZoneInfo("Asia/Kolkata")


def fixed_cutoff(value):
    day = date.fromisoformat(str(value))
    return datetime.combine(day, time.max, ZONE).astimezone(timezone.utc).replace(tzinfo=None)


def validate_deadline(rule, now=None):
    if rule.get("deadline_mode", "relative") == "fixed":
        if not rule.get("deadline_date"):
            raise DomainValidationError("Select a completion deadline date.")
        if fixed_cutoff(rule["deadline_date"]) <= (
            now or datetime.now(timezone.utc).replace(tzinfo=None)
        ):
            raise DomainValidationError(
                "The completion deadline date has passed. Select a current or future date."
            )


def resolve_deadline(rule, now):
    if rule.get("deadline_mode", "relative") == "fixed":
        return fixed_cutoff(rule["deadline_date"]).isoformat()
    return (now + timedelta(days=rule["deadline_days"])).isoformat()


def deadline_expired(rule):
    return rule.get("deadline_mode") == "fixed" and fixed_cutoff(
        rule["deadline_date"]
    ) <= datetime.now(timezone.utc).replace(tzinfo=None)
