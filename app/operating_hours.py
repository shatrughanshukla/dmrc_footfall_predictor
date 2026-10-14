"""Shared service-window rules used by forecasts and schedule recommendations."""

SERVICE_START_MINUTE = 5 * 60
SERVICE_END_MINUTE = 23 * 60 + 30


def is_service_operating(hour: int, minute: int = 0) -> bool:
    """Return whether the selected local time falls in the modeled service window."""
    minute_of_day = int(hour) * 60 + int(minute)
    return SERVICE_START_MINUTE <= minute_of_day < SERVICE_END_MINUTE
