import time


def calculate_wait_time(seconds, now=None):
    # Get seconds since the epoch.
    if now is None:
        now = time.time()

    # How far are we into the current interval?
    # Example: now=1668109003.7, seconds=10. remainder=3.7
    remainder = now % seconds

    # The time to wait is the interval duration minus how far we already are.
    # If remainder is 0 (we are perfectly on an interval), wait the full duration.
    if remainder == 0:
        wait_time = seconds
    else:
        wait_time = seconds - remainder

    return wait_time
