"""Opt-in limits for the small shared Render demo; desktop defaults stay intact."""
from functools import wraps
import os
from threading import RLock

HOSTED_DEMO = os.getenv('CRIMSON_HOSTED_DEMO') == '1'
CALCULATION_LOCK = RLock()


def one_calculation_at_a_time(function):
    """Avoid overlapping large numerical allocations in the single demo worker."""
    if not HOSTED_DEMO:
        return function
    @wraps(function)
    def wrapped(*args, **kwargs):
        with CALCULATION_LOCK:
            return function(*args, **kwargs)
    for name in ('cache_clear', 'cache_info', 'cache_parameters'):
        if hasattr(function, name):
            setattr(wrapped, name, getattr(function, name))
    return wrapped
