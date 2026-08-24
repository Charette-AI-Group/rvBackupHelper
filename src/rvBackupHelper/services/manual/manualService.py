"""Checking whether the published manual can actually be reached.

QDesktopServices.openUrl reports whether a browser *launched*, not whether the
page loaded. Without a check of its own, a machine with no network would be
handed a browser error page instead of the copy sitting on its own disk.
"""

from __future__ import annotations

import logging
import urllib.request

from rvBackupHelper import appConfig

logger = logging.getLogger(__name__)


class ManualService:
    """Asks the published manual whether it is there."""

    def __init__(self, opener=urllib.request.urlopen) -> None:
        self.opener = opener

    def isOnlineCopyAvailable(self, url: str | None = None) -> bool:
        """True when the published manual answers within the timeout.

        A HEAD request, so nothing is downloaded to answer the question. Any
        network failure is a negative rather than an error: the point is only
        to choose between two copies, and the local one is always a fine
        answer.
        """
        target = url or appConfig.manualUrl
        request = urllib.request.Request(target, method="HEAD")
        try:
            with self.opener(request, timeout=appConfig.manualTimeoutSeconds) as reply:
                # Some openers answer without a status; treat that as success.
                status = getattr(reply, "status", 200) or 200
                reachable = 200 <= status < 400
        except (OSError, ValueError) as exc:
            # URLError and HTTPError are both OSError; a malformed URL is a
            # ValueError. Either way the answer is the same.
            logger.info("Published manual not reachable: %s", exc)
            return False
        logger.info("Published manual answered %s", status)
        return reachable
