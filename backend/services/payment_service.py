from datetime import datetime, time, date

def parse_time_or_dt(val, ref_date=None):
    """Helper to parse a datetime or time string into a datetime object."""
    if isinstance(val, datetime):
        return val
    if ref_date is None:
        ref_date = date.today()
    elif isinstance(ref_date, str):
        try:
            ref_date = datetime.strptime(ref_date, "%Y-%m-%d").date()
        except ValueError:
            ref_date = date.today()

    if isinstance(val, time):
        return datetime.combine(ref_date, val)
    
    if isinstance(val, str):
        val = val.strip()
        # Clean ISO representations (remove Z, timezone offset, and fractional seconds)
        clean_val = val.replace('Z', '').split('+')[0]
        if '.' in clean_val:
            clean_val = clean_val.split('.')[0]

        # Try full datetime formats
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %I:%M %p",
            "%Y-%m-%d %I:%M:%S %p"
        ):
            try:
                return datetime.strptime(clean_val, fmt)
            except ValueError:
                pass

        # Try 12-hour AM/PM and 24-hour time formats
        for fmt in ("%I:%M %p", "%I:%M:%S %p", "%I:%M%p", "%I:%M:%S%p", "%H:%M:%S", "%H:%M"):
            try:
                t = datetime.strptime(val, fmt).time()
                return datetime.combine(ref_date, t)
            except ValueError:
                pass
    raise ValueError(f"Unable to parse time or datetime: {val}")

def calculate_payment(scheduled_start, scheduled_end, actual_start, actual_end, payment_per_worker, ref_date=None):
    """
    Smart payment calculation per QuickHire specification:
    - scheduled_hours = scheduled_end - scheduled_start
    - actual_hours = actual_end - actual_start
    - Case 1 (On time): actual_start <= scheduled_start and actual_hours >= scheduled_hours -> 100% pay, late=False
    - Case 2 (Late but completes full scheduled duration - stayed late): -> 100% pay, late=True
    - Case 3 (Late and leaves without completing full duration): -> payment = payment_per_worker * (actual_hours / scheduled_hours), late=True
    - Also handles on-time early departure: prorated payment, late=False.
    """
    dt_sched_start = parse_time_or_dt(scheduled_start, ref_date)
    dt_sched_end = parse_time_or_dt(scheduled_end, ref_date)
    dt_actual_start = parse_time_or_dt(actual_start, ref_date)
    dt_actual_end = parse_time_or_dt(actual_end, ref_date)

    scheduled_seconds = (dt_sched_end - dt_sched_start).total_seconds()
    actual_seconds = (dt_actual_end - dt_actual_start).total_seconds()

    if scheduled_seconds <= 0:
        scheduled_seconds = 3600.0 # fallback 1 hour

    if actual_seconds < 0:
        actual_seconds = 0.0

    scheduled_hours = round(scheduled_seconds / 3600.0, 2)
    actual_hours = round(actual_seconds / 3600.0, 2)
    scheduled_payment = float(payment_per_worker)

    # 3-minute grace period threshold for start time
    is_late = (dt_actual_start - dt_sched_start).total_seconds() > 180

    if not is_late:
        # Case 1: Arrived on time
        if actual_seconds >= (scheduled_seconds - 5):
            calculated_payment = scheduled_payment
            reason = f"Worker completed full scheduled duration ({actual_hours} hrs / {int(actual_seconds//60)}m). 100% payment approved."
        else:
            ratio = actual_seconds / scheduled_seconds if scheduled_seconds > 0 else 1.0
            calculated_payment = round(scheduled_payment * min(ratio, 1.0), 2)
            reason = f"Worker completed {actual_hours} of {scheduled_hours} scheduled hours."
    else:
        # Arrived late
        if actual_seconds >= (scheduled_seconds - 5):
            # Case 2: Late arrival but made up time
            calculated_payment = scheduled_payment
            reason = f"Worker arrived late but completed full duration ({actual_hours} hrs / {int(actual_seconds//60)}m). 100% payment approved."
        else:
            # Case 3: Late arrival and left early
            ratio = actual_seconds / scheduled_seconds if scheduled_seconds > 0 else 1.0
            calculated_payment = round(scheduled_payment * min(ratio, 1.0), 2)
            reason = f"Worker completed {actual_hours} of {scheduled_hours} scheduled hours."

    return {
        "scheduled_hours": scheduled_hours,
        "actual_hours": actual_hours,
        "scheduled_payment": scheduled_payment,
        "calculated_payment": calculated_payment,
        "late": is_late,
        "reason": reason
    }
