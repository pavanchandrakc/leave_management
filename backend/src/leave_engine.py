from datetime import date, timedelta
from typing import List, Tuple, Set
from sqlalchemy.orm import Session
from src.models import Holiday, LeaveType

def get_holiday_dates(session: Session, start_date: date, end_date: date) -> Set[date]:
    """Retrieve all holiday dates falling within the given date window [start_date, end_date]."""
    holidays = session.query(Holiday).filter(
        Holiday.holiday_date >= start_date,
        Holiday.holiday_date <= end_date
    ).all()
    return {h.holiday_date for h in holidays}

def calculate_leave_days(
    session: Session,
    start_date: date,
    end_date: date,
    leave_type: LeaveType
) -> Tuple[int, List[str]]:
    """
    Computes deductible days between start_date and end_date (inclusive) according to the
    leave type policy rules (counts_weekends, counts_holidays).
    
    Returns:
        (deductible_days, breakdown_notes)
    """
    if end_date < start_date:
        return 0, ["End date cannot be earlier than start date."]

    counts_weekends = getattr(leave_type, "counts_weekends", False)
    counts_holidays = getattr(leave_type, "counts_holidays", False)

    # Pre-fetch holidays in this range if not counted
    holiday_dates = set()
    if not counts_holidays:
        holiday_dates = get_holiday_dates(session, start_date, end_date)

    deductible_days = 0
    breakdown_notes = []

    curr = start_date
    while curr <= end_date:
        is_weekend = curr.weekday() in (5, 6) # 5 = Saturday, 6 = Sunday
        is_holiday = curr in holiday_dates

        if is_weekend and not counts_weekends:
            breakdown_notes.append(f"{curr.isoformat()} skipped (weekend)")
        elif is_holiday and not counts_holidays:
            breakdown_notes.append(f"{curr.isoformat()} skipped (public holiday)")
        else:
            deductible_days += 1

        curr += timedelta(days=1)

    return deductible_days, breakdown_notes
