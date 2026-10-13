"""Delhi date context used consistently by simulation, training, and inference.

Festival impacts are scenario categories, not measured passenger responses.
The 2026 public-holiday dates follow the GNCTD holiday notification. Dates for
2027–2028 are festival-calendar observances; work-closure status is not assumed
until an official Delhi holiday notice is available.
"""
from datetime import date


def _occasion(name, category, *, public_holiday=False, source=""):
    return {
        "name": name,
        "category": category,
        "holiday_type": {"NATIONAL": 1, "FESTIVAL": 2, "PEAK_FESTIVAL": 3,
                         "SHOPPING_PEAK": 4, "LEISURE_PEAK": 4}[category],
        "is_public_holiday": public_holiday,
        "source": source,
    }


_PROJECT_2025 = "Project synthetic calendar (2025 scenario assumptions)"
_GNCTD_2026 = "GNCTD 2026 holiday notification"
_PANCHANG_FUTURE = "Delhi festival calendar; office closure unconfirmed"

OCCASIONS = {
    # Dates/events used to construct the existing 2025 synthetic scenarios.
    date(2025, 1, 26): _occasion("Republic Day", "NATIONAL", public_holiday=True, source=_PROJECT_2025),
    date(2025, 3, 14): _occasion("Holi", "FESTIVAL", public_holiday=True, source=_PROJECT_2025),
    date(2025, 3, 31): _occasion("Eid-ul-Fitr", "FESTIVAL", public_holiday=True, source=_PROJECT_2025),
    date(2025, 8, 9): _occasion("Raksha Bandhan", "PEAK_FESTIVAL", source=_PROJECT_2025),
    date(2025, 8, 15): _occasion("Independence Day", "NATIONAL", public_holiday=True, source=_PROJECT_2025),
    date(2025, 10, 2): _occasion("Gandhi Jayanti / Dussehra", "NATIONAL", public_holiday=True, source=_PROJECT_2025),
    date(2025, 10, 20): _occasion("Karwa Chauth shopping period", "SHOPPING_PEAK", source=_PROJECT_2025),
    date(2025, 10, 22): _occasion("Diwali", "FESTIVAL", public_holiday=True, source=_PROJECT_2025),
    date(2025, 10, 23): _occasion("Bhai Dooj", "PEAK_FESTIVAL", public_holiday=True, source=_PROJECT_2025),
    date(2025, 10, 27): _occasion("Chhath Puja", "FESTIVAL", source=_PROJECT_2025),
    date(2025, 12, 25): _occasion("Christmas", "LEISURE_PEAK", public_holiday=True, source=_PROJECT_2025),
    date(2025, 12, 31): _occasion("New Year's Eve", "LEISURE_PEAK", source=_PROJECT_2025),

    # Major Delhi gazetted holidays and requested festivals for 2026.
    date(2026, 1, 26): _occasion("Republic Day", "NATIONAL", public_holiday=True, source=_GNCTD_2026),
    date(2026, 3, 4): _occasion("Holi", "FESTIVAL", public_holiday=True, source=_GNCTD_2026),
    date(2026, 8, 15): _occasion("Independence Day", "NATIONAL", public_holiday=True, source=_GNCTD_2026),
    date(2026, 8, 28): _occasion("Raksha Bandhan", "PEAK_FESTIVAL", source=_GNCTD_2026),
    date(2026, 9, 4): _occasion("Krishna Janmashtami", "FESTIVAL", public_holiday=True, source=_GNCTD_2026),
    date(2026, 10, 2): _occasion("Gandhi Jayanti", "NATIONAL", public_holiday=True, source=_GNCTD_2026),
    date(2026, 10, 20): _occasion("Dussehra", "NATIONAL", public_holiday=True, source=_GNCTD_2026),
    date(2026, 11, 8): _occasion("Diwali", "FESTIVAL", public_holiday=True, source=_GNCTD_2026),
    date(2026, 11, 24): _occasion("Guru Nanak Jayanti", "FESTIVAL", public_holiday=True, source=_GNCTD_2026),
    date(2026, 12, 25): _occasion("Christmas", "LEISURE_PEAK", public_holiday=True, source=_GNCTD_2026),

    # Upcoming lunar festival dates for Delhi; future office closures are not
    # asserted. They activate a learned event-class scenario in the model.
    date(2027, 3, 22): _occasion("Holi", "FESTIVAL", source=_PANCHANG_FUTURE),
    date(2027, 8, 17): _occasion("Raksha Bandhan", "PEAK_FESTIVAL", source=_PANCHANG_FUTURE),
    date(2027, 8, 25): _occasion("Krishna Janmashtami", "FESTIVAL", source=_PANCHANG_FUTURE),
    date(2027, 10, 9): _occasion("Dussehra", "NATIONAL", source=_PANCHANG_FUTURE),
    date(2027, 10, 29): _occasion("Diwali", "FESTIVAL", source=_PANCHANG_FUTURE),
    date(2028, 8, 5): _occasion("Raksha Bandhan", "PEAK_FESTIVAL", source=_PANCHANG_FUTURE),
    date(2028, 9, 27): _occasion("Dussehra", "NATIONAL", source=_PANCHANG_FUTURE),
    date(2028, 10, 17): _occasion("Diwali", "FESTIVAL", source=_PANCHANG_FUTURE),
    date(2028, 8, 13): _occasion("Krishna Janmashtami", "FESTIVAL", source=_PANCHANG_FUTURE),
    date(2029, 9, 1): _occasion("Krishna Janmashtami", "FESTIVAL", source=_PANCHANG_FUTURE),
    date(2030, 8, 21): _occasion("Krishna Janmashtami", "FESTIVAL", source=_PANCHANG_FUTURE),
    date(2031, 8, 9): _occasion("Krishna Janmashtami", "FESTIVAL", source=_PANCHANG_FUTURE),
    date(2032, 8, 28): _occasion("Krishna Janmashtami", "FESTIVAL", source=_PANCHANG_FUTURE),
    date(2033, 8, 17): _occasion("Krishna Janmashtami", "FESTIVAL", source=_PANCHANG_FUTURE),
}

for _year in range(2025, 2036):
    for _month, _day, _name in (
        (1, 26, "Republic Day"),
        (8, 15, "Independence Day"),
        (10, 2, "Gandhi Jayanti"),
        (12, 25, "Christmas"),
    ):
        OCCASIONS.setdefault(
            date(_year, _month, _day),
            _occasion(_name, "NATIONAL" if _name != "Christmas" else "LEISURE_PEAK",
                      public_holiday=True, source="Fixed annual date; holiday effect is a scenario assumption")
        )


def get_calendar_context(day: date) -> dict:
    """Return weekday, workday, occasion, and model event features for a date."""
    event = OCCASIONS.get(day)
    weekend = day.weekday() >= 5
    public_holiday = bool(event and event["is_public_holiday"])
    workday = not weekend and not public_holiday
    if weekend:
        day_status = "Weekend"
    elif public_holiday:
        day_status = "Delhi public holiday"
    elif event:
        day_status = "Weekday; festival listed, office closure unconfirmed"
    else:
        day_status = "Weekday workday"
    return {
        "date": day.isoformat(),
        "weekday": day.strftime("%A"),
        "is_weekend": weekend,
        "is_workday": workday,
        "is_public_holiday": public_holiday,
        "day_status": day_status,
        "occasion": event["name"] if event else None,
        "occasion_category": event["category"] if event else None,
        "holiday_type": event["holiday_type"] if event else 0,
        "calendar_source": event["source"] if event else None,
        "occasion_coverage": "major occasions are explicitly listed by date; weekday is computed for any date",
    }
