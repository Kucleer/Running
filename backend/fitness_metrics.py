"""Fitness metrics calculations for VO2max estimation.

Uses ACSM metabolic equation for horizontal running + heart rate reserve
to estimate VO2max from submaximal running data.
"""


def estimate_vo2max_from_activity(distance_m, duration_s, avg_hr, resting_hr, max_hr):
    """Estimate VO2max from a single activity using ACSM + HR reserve.

    Args:
        distance_m: Activity distance in meters
        duration_s: Activity duration in seconds
        avg_hr: Average heart rate during activity (bpm)
        resting_hr: Resting heart rate (bpm)
        max_hr: Maximum heart rate (bpm)

    Returns:
        Estimated VO2max in mL/kg/min, or None if data insufficient
    """
    # Validate inputs
    if not all([distance_m, duration_s, avg_hr, resting_hr, max_hr]):
        return None
    if distance_m <= 0 or duration_s <= 0:
        return None
    if avg_hr <= 0 or resting_hr <= 0 or max_hr <= 0:
        return None
    if max_hr <= resting_hr:
        return None

    # Calculate running speed in m/min
    speed_m_min = (distance_m / duration_s) * 60

    # Skip very slow runs (walking pace)
    if speed_m_min < 80:  # slower than ~8:20/km
        return None

    # ACSM metabolic equation for horizontal running:
    # VO2 (mL/kg/min) = 0.2 * speed (m/min) + 0.9 * speed * grade + 3.5
    # For flat running (grade=0): VO2 = 0.2 * speed + 3.5
    vo2_at_pace = 0.2 * speed_m_min + 3.5

    # Calculate heart rate fraction (HR reserve method)
    hr_reserve = max_hr - resting_hr
    hr_fraction = (avg_hr - resting_hr) / hr_reserve

    # Only use if HR is in valid submaximal range
    # Too low = not effort, too high = anaerobic/invalid
    if hr_fraction < 0.55 or hr_fraction > 0.92:
        return None

    # Estimate VO2max: VO2 at pace / HR fraction
    vo2max_estimate = vo2_at_pace / hr_fraction

    # Clamp to reasonable range
    if vo2max_estimate < 20 or vo2max_estimate > 80:
        return None

    return round(vo2max_estimate, 2)


def estimate_vo2max_from_hr(resting_hr, max_hr):
    """Estimate VO2max using Uth heart rate ratio method.

    Formula: VO2max ≈ 15.3 * (HRmax / HRrest)
    Less accurate than activity-based estimation, but provides baseline.

    Args:
        resting_hr: Resting heart rate (bpm)
        max_hr: Maximum heart rate (bpm)

    Returns:
        Estimated VO2max in mL/kg/min, or None if data insufficient
    """
    if not resting_hr or not max_hr:
        return None
    if resting_hr <= 0 or max_hr <= 0:
        return None
    if max_hr <= resting_hr:
        return None

    vo2max = 15.3 * (max_hr / resting_hr)

    # Clamp to reasonable range
    if vo2max < 20 or vo2max > 80:
        return None

    return round(vo2max, 2)


def calc_median(values):
    """Calculate median of a list of numbers."""
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n % 2 == 1:
        return sorted_vals[n // 2]
    else:
        return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2
