from ua_parser import parse

from backend.metrics.events import DeviceType

_MOBILE_OS_FAMILIES: frozenset[str] = frozenset({"Android", "iOS"})


def classify_user_agent(ua_string: str | None) -> DeviceType:
    if not ua_string:
        return DeviceType.DESKTOP
    result = parse(ua_string)
    os_family = result.os.family if result.os else None
    # os.family is more reliable than device.family for the binary mobile/desktop split.
    return DeviceType.MOBILE if os_family in _MOBILE_OS_FAMILIES else DeviceType.DESKTOP
