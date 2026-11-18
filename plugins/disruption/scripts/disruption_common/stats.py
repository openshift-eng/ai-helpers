"""Statistics shared by the disruption skills, so every report computes them the same way."""
import math


def percentile(values, q):
    """Linear-interpolated percentile (q in 0..100) of values, or None when there are none."""
    ordered = sorted(values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * q / 100.0
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)
