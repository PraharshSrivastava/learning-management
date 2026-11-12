"""Guard file-location-dependent asset paths.

These assets are looked up relative to the module's own file. If a module
moves, the lookup must still find the file, or the feature silently degrades
(for example a certificate without its logo).
"""

from app.modules.journeys.certificates import LOGO_PATH


def test_journey_certificate_logo_exists():
    assert LOGO_PATH.is_file(), LOGO_PATH
