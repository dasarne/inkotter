from __future__ import annotations

import errno
import unittest

from inkotter.transport.errors import (
    REASON_CONNECTION_REFUSED,
    REASON_HOST_DOWN,
    REASON_NETWORK_UNREACHABLE,
    REASON_NO_ROUTE,
    REASON_TIMEOUT,
    REASON_UNKNOWN,
    classify_transport_error_message,
    classify_transport_os_error,
)


class TransportErrorClassificationTests(unittest.TestCase):
    def test_classify_transport_error_message_by_text(self) -> None:
        self.assertEqual(classify_transport_error_message("timed out")[0], REASON_TIMEOUT)
        self.assertEqual(classify_transport_error_message("No route to host")[0], REASON_NO_ROUTE)
        self.assertEqual(classify_transport_error_message("Connection refused")[0], REASON_CONNECTION_REFUSED)
        self.assertEqual(classify_transport_error_message("Network is unreachable")[0], REASON_NETWORK_UNREACHABLE)
        self.assertEqual(classify_transport_error_message("Host is down")[0], REASON_HOST_DOWN)
        self.assertEqual(classify_transport_error_message("weird io failure")[0], REASON_UNKNOWN)

    def test_classify_transport_os_error_prefers_errno(self) -> None:
        timeout_error = OSError(errno.ETIMEDOUT, "foo")
        self.assertEqual(classify_transport_os_error(timeout_error)[0], REASON_TIMEOUT)

        no_route_error = OSError(errno.EHOSTUNREACH, "bar")
        self.assertEqual(classify_transport_os_error(no_route_error)[0], REASON_NO_ROUTE)

        refused_error = OSError(errno.ECONNREFUSED, "baz")
        self.assertEqual(classify_transport_os_error(refused_error)[0], REASON_CONNECTION_REFUSED)

        network_error = OSError(errno.ENETUNREACH, "qux")
        self.assertEqual(classify_transport_os_error(network_error)[0], REASON_NETWORK_UNREACHABLE)

        host_down_error = OSError(errno.EHOSTDOWN, "quux")
        self.assertEqual(classify_transport_os_error(host_down_error)[0], REASON_HOST_DOWN)

    def test_classify_transport_os_error_falls_back_to_message(self) -> None:
        unknown_errno_timeout_text = OSError(9999, "timed out")
        reason, details = classify_transport_os_error(unknown_errno_timeout_text)
        self.assertEqual(reason, REASON_TIMEOUT)
        self.assertEqual(details, "[Errno 9999] timed out")


if __name__ == "__main__":
    unittest.main()
