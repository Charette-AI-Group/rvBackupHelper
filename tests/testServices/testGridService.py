"""Tests for turning the Arduino's overlay on and off."""

from __future__ import annotations

import pytest
import serial

from rvBackupHelper import appConfig
from rvBackupHelper.services.board.gridService import (
    BoardError,
    GridService,
    findBoardPort,
)


class FakeLink:
    """Stands in for serial.Serial, recording what was written."""

    def __init__(self, reply: bytes = b"grid off\r\n", failOnWrite: bool = False) -> None:
        self.reply = reply
        self.failOnWrite = failOnWrite
        self.written = b""
        self.flushed = False
        self.inputReset = False
        self.closed = False

    def __enter__(self) -> FakeLink:
        return self

    def __exit__(self, *exc) -> None:
        self.closed = True

    def reset_input_buffer(self) -> None:
        self.inputReset = True

    def write(self, payload: bytes) -> None:
        if self.failOnWrite:
            raise serial.SerialException("port disappeared")
        self.written += payload

    def flush(self) -> None:
        self.flushed = True

    def readline(self) -> bytes:
        return self.reply


def serviceWith(link: FakeLink, port: str | None = "COM9") -> GridService:
    return GridService(
        portFinder=lambda: port,
        serialFactory=lambda *args, **kwargs: link,
    )


@pytest.fixture(autouse=True)
def noResetWait(monkeypatch):
    """The real service waits out the board's reset; tests should not."""
    monkeypatch.setattr(appConfig, "boardResetSeconds", 0.0)


def testHidingTheGridSendsTheOffCommand() -> None:
    link = FakeLink(reply=b"grid off\r\n")
    service = serviceWith(link)

    reply = service.setGridVisible(False)

    assert link.written == appConfig.gridOffCommand.encode("ascii")
    assert reply == "grid off"


def testShowingTheGridSendsTheOnCommand() -> None:
    link = FakeLink(reply=b"grid on\r\n")

    reply = serviceWith(link).setGridVisible(True)

    assert link.written == appConfig.gridOnCommand.encode("ascii")
    assert reply == "grid on"


def testQueryingAsksWithoutChangingAnything() -> None:
    link = FakeLink(reply=b"grid on\r\n")

    serviceWith(link).readGridState()

    assert link.written == appConfig.gridQueryCommand.encode("ascii")


def testStaleRepliesAreDiscardedBeforeAsking() -> None:
    """The board chatters on reset; the reply read must be to our command."""
    link = FakeLink()

    serviceWith(link).setGridVisible(False)

    assert link.inputReset
    assert link.flushed


def testThePortIsAlwaysReleased() -> None:
    """Holding the port would stop arduino-cli uploading."""
    link = FakeLink()

    serviceWith(link).setGridVisible(False)

    assert link.closed


def testNoBoardIsReportedHelpfully() -> None:
    service = serviceWith(FakeLink(), port=None)

    with pytest.raises(BoardError, match="No Arduino found"):
        service.setGridVisible(False)


def testASerialFailureIsWrapped() -> None:
    service = serviceWith(FakeLink(failOnWrite=True))

    with pytest.raises(BoardError, match="Could not talk to the board on COM9"):
        service.setGridVisible(False)


def testSilenceListsItsCausesInOrder() -> None:
    """Silence reads as a serial fault and is usually something else.

    The causes are ranked because the ranking has already changed once: the
    stock TVout was the likely one until the libraries were committed to the
    repository, and leading with it after that sent the reader the wrong way.
    """
    service = serviceWith(FakeLink(reply=b""))

    with pytest.raises(BoardError) as raised:
        service.setGridVisible(False)

    message = str(raised.value)
    assert message.index("not running the generated grid sketch") < message.index(
        "stock TVout"
    )


def testSilenceOpensWithOneShortLine() -> None:
    """The first line is all a status bar can hold, and this message was cut

    in half by one - at "the Video Experimenter fc", losing every instruction
    it carried.
    """
    service = serviceWith(FakeLink(reply=b""))

    with pytest.raises(BoardError) as raised:
        service.setGridVisible(False)

    headline = str(raised.value).splitlines()[0]
    assert headline == "The board did not answer on COM9."
    # Roughly what the bar holds; the exact figure lives in the dialog helper,
    # and a service test has no business importing from the interface layer.
    assert len(headline) <= 100


def testBoardIsFoundByVendorId(monkeypatch) -> None:
    class Port:
        def __init__(self, device, vid, description):
            self.device, self.vid, self.description = device, vid, description

    monkeypatch.setattr(
        "rvBackupHelper.services.board.gridService.list_ports.comports",
        lambda: [
            Port("COM1", 0x1234, "Some modem"),
            Port("COM3", 0x2341, "Arduino Uno (COM3)"),
        ],
    )

    assert findBoardPort() == "COM3"


def testBoardIsFoundByNameWhenTheVendorIdIsUnfamiliar(monkeypatch) -> None:
    class Port:
        def __init__(self, device, vid, description):
            self.device, self.vid, self.description = device, vid, description

    monkeypatch.setattr(
        "rvBackupHelper.services.board.gridService.list_ports.comports",
        lambda: [Port("COM7", 0x9999, "Arduino Uno clone")],
    )

    assert findBoardPort() == "COM7"


def testNoBoardFoundReturnsNone(monkeypatch) -> None:
    monkeypatch.setattr(
        "rvBackupHelper.services.board.gridService.list_ports.comports", lambda: []
    )

    assert findBoardPort() is None
