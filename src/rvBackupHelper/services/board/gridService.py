"""Turning the Arduino's overlay on and off.

A grid burned into calibration footage hides the very markings you are trying
to click, so being able to blank it without unplugging anything matters.

The port is opened and closed for each command on purpose. Holding it open
would be faster, but it would also keep arduino-cli from uploading, and the
board keeps its state in EEPROM so nothing is lost by letting go.
"""

from __future__ import annotations

import logging
import time

import serial
from serial.tools import list_ports

from rvBackupHelper import appConfig

logger = logging.getLogger(__name__)


class BoardError(RuntimeError):
    """The board could not be found, opened, or did not answer."""


def findBoardPort() -> str | None:
    """The serial port the Arduino is on, or None if it is not plugged in."""
    for port in list_ports.comports():
        if port.vid in appConfig.boardVendorIds:
            return port.device
    # Fall back to the description for boards with an unfamiliar vendor id.
    for port in list_ports.comports():
        if "arduino" in (port.description or "").lower():
            return port.device
    return None


class GridService:
    """Sends single-character commands to the sketch and reads its reply."""

    def __init__(self, portFinder=findBoardPort, serialFactory=serial.Serial) -> None:
        self.portFinder = portFinder
        self.serialFactory = serialFactory

    def setGridVisible(self, visible: bool) -> str:
        command = (
            appConfig.gridOnCommand if visible else appConfig.gridOffCommand
        )
        return self.sendCommand(command)

    def readGridState(self) -> str:
        return self.sendCommand(appConfig.gridQueryCommand)

    def sendCommand(self, command: str) -> str:
        port = self.portFinder()
        if port is None:
            raise BoardError(
                "No Arduino found. Check it is plugged in, and that nothing "
                "else (the Arduino IDE's serial monitor) is holding the port."
            )
        try:
            return self.exchange(port, command)
        except serial.SerialException as exc:
            logger.warning("Serial exchange failed on %s: %s", port, exc)
            raise BoardError(f"Could not talk to the board on {port}: {exc}") from exc

    def exchange(self, port: str, command: str) -> str:
        with self.serialFactory(
            port, appConfig.commandBaud, timeout=appConfig.serialTimeoutSeconds
        ) as link:
            # Opening the port resets the board; the sketch is not listening
            # until the bootloader has handed over.
            time.sleep(appConfig.boardResetSeconds)
            link.reset_input_buffer()
            link.write(command.encode("ascii"))
            link.flush()
            reply = link.readline().decode("ascii", errors="replace").strip()
        if not reply:
            # One short first line, then the causes: the first line is all a
            # status bar can hold, and this message has already been cut in
            # half once by one.
            raise BoardError(
                f"The board did not answer on {port}.\n\n"
                "The port opened, so it is the sketch on the board that did not "
                "reply. In rough order of likelihood:\n\n"
                "1. The board is not running the generated grid sketch. Upload it "
                "again from the Calibrate tab - the bring-up sketch is silent "
                "because it accepts no commands at all.\n"
                "2. Something else is holding the port: the Arduino IDE's serial "
                "monitor, or a second copy of this application.\n"
                "3. The sketch was built against the stock TVout, which leaves the "
                "board resetting on every sync pulse. Help > Check Toolchain shows "
                "which libraries a build uses; they now ship with the repository, "
                "so this is the least likely of the three."
            )
        logger.info("Board replied %r to %r", reply, command)
        return reply
