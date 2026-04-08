"""Shared transport error classification helpers."""

from __future__ import annotations

import errno


REASON_TIMEOUT = "timeout"
REASON_NO_ROUTE = "no_route"
REASON_CONNECTION_REFUSED = "connection_refused"
REASON_NETWORK_UNREACHABLE = "network_unreachable"
REASON_HOST_DOWN = "host_down"
REASON_UNKNOWN = "unknown"


def classify_transport_os_error(exc: OSError) -> tuple[str, str]:
    details = str(exc).strip() or exc.__class__.__name__
    by_errno = _reason_from_errno(exc.errno)
    if by_errno is not None:
        return by_errno, details
    return classify_transport_error_message(details)


def classify_transport_error_message(message: str) -> tuple[str, str]:
    details = (message or "").strip() or "unknown transport error"
    lowered = details.casefold()
    if "timed out" in lowered or "timeout" in lowered:
        return REASON_TIMEOUT, details
    if "no route to host" in lowered:
        return REASON_NO_ROUTE, details
    if "connection refused" in lowered:
        return REASON_CONNECTION_REFUSED, details
    if "network is unreachable" in lowered:
        return REASON_NETWORK_UNREACHABLE, details
    if "host is down" in lowered:
        return REASON_HOST_DOWN, details
    return REASON_UNKNOWN, details


def _reason_from_errno(error_number: int | None) -> str | None:
    if error_number is None:
        return None
    if error_number == errno.ETIMEDOUT:
        return REASON_TIMEOUT
    if error_number == errno.EHOSTUNREACH:
        return REASON_NO_ROUTE
    if error_number == errno.ECONNREFUSED:
        return REASON_CONNECTION_REFUSED
    if error_number == errno.ENETUNREACH:
        return REASON_NETWORK_UNREACHABLE
    if error_number == errno.EHOSTDOWN:
        return REASON_HOST_DOWN
    return None
