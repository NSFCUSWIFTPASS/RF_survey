import pytest
from datetime import datetime
from utils.scheduler import calculate_wait_time

# A fixed timestamp for our tests to use as "now"
BASE_TIME = datetime(2023, 10, 27, 12, 30, 13, 123456)


@pytest.mark.parametrize(
    "current_timestamp, interval_seconds, expected_wait_time",
    [
        # --- Basic Case ---
        # At 1003.7 seconds, the next 10-second interval is at 1010.0.
        # We are 3.7s into the interval, so we need to wait 6.3s.
        (1003.7, 10.0, 6.3),
        # --- Boundary Case: Exactly on an interval ---
        # At 1000.0 seconds, the next 10-second interval is at 1010.0.
        # The code should wait the full 10 seconds.
        (1000.0, 10.0, 10.0),
        # --- Boundary Case: Just after an interval ---
        # A tiny fraction of a second past the interval. The wait time should be
        # almost the full interval.
        (1000.000001, 10.0, 9.999999),
        # --- Sub-second Interval ---
        # At 1000.8 seconds, the next 0.5-second interval is at 1001.0.
        # We are 0.3s into the current 0.5s window (from 1000.5 to 1001.0).
        # We need to wait 0.2s.
        (1000.8, 0.5, 0.2),
        # --- Realistic Timestamp ---
        # A real timestamp for Feb 28, 2023. We want to snap to the next full minute (60s).
        # 1677695345.25 % 60 = 5.25. We need to wait 60 - 5.25 = 54.75 seconds.
        (1677695345.25, 60.0, 54.75),
    ],
)
def test_calculate_wait_time(current_timestamp, interval_seconds, expected_wait_time):
    """
    Verifies that the wait time calculation is correct for various scenarios.
    """
    # ACT
    actual_wait_time = calculate_wait_time(interval_seconds, current_timestamp)

    # ASSERT
    # Use pytest.approx for safe floating-point comparison.
    assert actual_wait_time == pytest.approx(expected_wait_time)
