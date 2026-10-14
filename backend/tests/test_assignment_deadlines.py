from datetime import datetime

import pytest

from app.core.exceptions import DomainValidationError
from app.services.assignment_deadlines import fixed_cutoff, resolve_deadline, validate_deadline


def test_fixed_date_is_end_of_day_in_kolkata():
    assert fixed_cutoff("2026-10-31") == datetime(2026, 10, 31, 18, 29, 59, 999999)


def test_relative_deadline_keeps_existing_behavior():
    assert (
        resolve_deadline({"deadline_days": 7}, datetime(2026, 10, 7, 12)) == "2026-10-14T12:00:00"
    )


def test_fixed_deadline_validation_at_cutoff():
    rule = {"deadline_mode": "fixed", "deadline_date": "2026-10-31"}
    validate_deadline(rule, datetime(2026, 10, 31, 18, 29, 58))
    with pytest.raises(DomainValidationError):
        validate_deadline(rule, datetime(2026, 10, 31, 18, 30))
    with pytest.raises(DomainValidationError):
        validate_deadline({"deadline_mode": "fixed"})
