from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def truncate_to_milliseconds(value: datetime) -> datetime:
    """Return ``value`` in UTC with sub-millisecond precision dropped.

    Shared by the UTub summary serializer and the server-side sort keys so the
    browser (which only parses milliseconds) and the server tie on identical rows.
    A naive value is treated as UTC.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.replace(microsecond=(value.microsecond // 1000) * 1000)


def to_iso_milliseconds(value: datetime) -> str:
    """ISO-8601 string in UTC, millisecond precision, explicit ``+00:00`` offset."""
    return truncate_to_milliseconds(value).isoformat(timespec="milliseconds")
