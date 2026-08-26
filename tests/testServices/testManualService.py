"""Tests for deciding whether the published manual can be reached."""

from __future__ import annotations

import urllib.error

import pytest

from rvBackupHelper import appConfig
from rvBackupHelper.services.manual.manualService import ManualService


class FakeReply:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self) -> FakeReply:
        return self

    def __exit__(self, *exc) -> None:
        return None


def openerReturning(status: int = 200, recorder: list | None = None):
    def opener(request, timeout=None):
        if recorder is not None:
            recorder.append((request.full_url, request.get_method(), timeout))
        return FakeReply(status)

    return opener


def openerRaising(error: Exception):
    def opener(request, timeout=None):
        raise error

    return opener


def testAnAnsweringPageIsAvailable() -> None:
    assert ManualService(openerReturning(200)).isOnlineCopyAvailable()


def testItAsksWithHeadAndItsOwnTimeout() -> None:
    """Nothing is downloaded to answer the question."""
    calls: list = []

    ManualService(openerReturning(200, calls)).isOnlineCopyAvailable()

    url, method, timeout = calls[0]
    assert url == appConfig.manualUrl
    assert method == "HEAD"
    assert timeout == appConfig.manualTimeoutSeconds


def testAMissingPageIsNotAvailable() -> None:
    notFound = urllib.error.HTTPError(
        appConfig.manualUrl, 404, "Not Found", {}, None
    )

    assert not ManualService(openerRaising(notFound)).isOnlineCopyAvailable()


def testNoNetworkIsNotAvailableRatherThanAnError() -> None:
    """Offline is an ordinary answer here, not a failure to report."""
    offline = urllib.error.URLError("getaddrinfo failed")

    assert not ManualService(openerRaising(offline)).isOnlineCopyAvailable()


def testATimeoutIsNotAvailable() -> None:
    assert not ManualService(openerRaising(TimeoutError())).isOnlineCopyAvailable()


def testAMalformedUrlIsNotAvailable() -> None:
    """A real malformed URL, not a faked raise from the opener.

    Request() rejects a URL with no scheme before any opener is called, so
    faking it here passed while the real path raised straight out of the
    worker thread. This case has to be built rather than mocked.
    """
    assert not ManualService(openerReturning(200)).isOnlineCopyAvailable("not-a-url")


def testAnOpenerRaisingAValueErrorIsAlsoJustAnAnswer() -> None:
    assert not ManualService(openerRaising(ValueError("unknown url type"))).isOnlineCopyAvailable()


@pytest.mark.parametrize("status", [200, 301, 302])
def testRedirectsCountAsReachable(status: int) -> None:
    assert ManualService(openerReturning(status)).isOnlineCopyAvailable()


@pytest.mark.parametrize("status", [404, 500])
def testErrorStatusesDoNot(status: int) -> None:
    assert not ManualService(openerReturning(status)).isOnlineCopyAvailable()
