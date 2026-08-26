<#
.SYNOPSIS
    Is the hardware this application needs plugged into this machine?

.DESCRIPTION
    Answers before anything is installed. It uses only Get-PnpDevice, which
    ships with Windows, so an installer can run it on its first page - long
    before Python, PySide6 or arduino-cli exist on the machine. The
    application runs this same script for Help > Check Hardware, so the
    verdict is identical whether it is asked during setup or a year later.

    What it can and cannot see is worth knowing:

      - It identifies a genuine board by USB PID, so an Uno R4, a Leonardo or
        a Mega is caught by name. The grid sketch will not run on any of them.
      - A CH340 clone reports only the CH340. A clone Uno and a clone Mega are
        indistinguishable, so those are reported as unverifiable rather than
        as good.
      - The Video Experimenter shield cannot be detected at all. It is a
        passive daughterboard and enumerates nothing. A board being present
        never means the shield is on it.
      - Whether the camera is composite or AHD is invisible from here. That is
        still the go/no-go test at the vehicle.

.PARAMETER Json
    Emit a machine-readable object instead of text. Used by the application.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File tools\checkHardware.ps1

.NOTES
    Exit code 0 when a usable board and a capture device were both found,
    1 otherwise. Warnings alone do not fail it: the calibrate-and-generate
    half of the application needs no hardware whatsoever.
#>

[CmdletBinding()]
param(
    [switch]$Json
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Boards this sketch actually runs on. TVout is hand-written AVR assembly
# driving ATmega328P timers.
$supportedBoards = @{
    '2341:0043' = 'Arduino Uno R3'
    '2341:0001' = 'Arduino Uno'
    '2A03:0043' = 'Arduino Uno R3 (arduino.org)'
    '2A03:0001' = 'Arduino Uno (arduino.org)'
}

# Boards worth naming when refusing, because "wrong board" is a much more
# useful message than "unrecognised". Not exhaustive, and deliberately not
# treated as such: anything unlisted warns rather than being rejected.
$knownWrongBoards = @{
    '2341:0069' = 'Arduino Uno R4 Minima'
    '2341:1002' = 'Arduino Uno R4 WiFi'
    '2341:8036' = 'Arduino Leonardo'
    '2341:0042' = 'Arduino Mega 2560'
    '2341:0010' = 'Arduino Mega 2560 R2'
    '2341:003D' = 'Arduino Due'
    '2341:003F' = 'Arduino Due (programming port)'
}

# The USB-to-serial bridge most clones use. It says nothing about the board.
$clonesVendorId = '1A86'
$arduinoVendorIds = @('2341', '2A03')

function Get-IdPair {
    param([string]$InstanceId)
    if ($InstanceId -match 'VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})') {
        return @{ Vid = $Matches[1].ToUpper(); Pid = $Matches[2].ToUpper() }
    }
    return $null
}

function Get-PortName {
    param([string]$FriendlyName)
    # Windows puts the port in the friendly name: "Arduino Uno (COM3)".
    if ($FriendlyName -match '\((COM\d+)\)') { return $Matches[1] }
    return ''
}

function Get-BoardResult {
    $ports = @(Get-PnpDevice -Class Ports -PresentOnly -ErrorAction SilentlyContinue)
    foreach ($device in $ports) {
        $ids = Get-IdPair -InstanceId $device.InstanceId
        if ($null -eq $ids) { continue }
        $key = "$($ids.Vid):$($ids.Pid)"
        $port = Get-PortName -FriendlyName $device.FriendlyName

        if ($supportedBoards.ContainsKey($key)) {
            return [ordered]@{
                found = $true; usable = $true; verdict = 'ok'
                model = $supportedBoards[$key]
                name = $device.FriendlyName; port = $port; id = $key
                message = "$($supportedBoards[$key]) on $port."
            }
        }
        if ($knownWrongBoards.ContainsKey($key)) {
            return [ordered]@{
                found = $true; usable = $false; verdict = 'wrongBoard'
                model = $knownWrongBoards[$key]
                name = $device.FriendlyName; port = $port; id = $key
                message = "$($knownWrongBoards[$key]) found on $port. The grid sketch runs only on an Uno R3 or Duemilanove (ATmega328P): TVout is hand-written AVR assembly driving that chip's timers."
            }
        }
        if ($ids.Vid -eq $clonesVendorId) {
            return [ordered]@{
                found = $true; usable = $true; verdict = 'clone'
                model = 'CH340 clone'
                name = $device.FriendlyName; port = $port; id = $key
                message = "A CH340 board on $port. Clones report only the USB bridge, so this cannot be confirmed as an Uno - a clone Mega looks identical. Upload will tell you."
            }
        }
        if ($arduinoVendorIds -contains $ids.Vid) {
            return [ordered]@{
                found = $true; usable = $true; verdict = 'unknownModel'
                model = 'unrecognised Arduino'
                name = $device.FriendlyName; port = $port; id = $key
                message = "An Arduino-branded board on $port that this check does not recognise ($key). It may not be an Uno; the list here is not exhaustive, so this is a warning rather than a refusal."
            }
        }
    }
    return [ordered]@{
        found = $false; usable = $false; verdict = 'missing'
        model = ''; name = ''; port = ''; id = ''
        message = 'No Arduino found. Plug the board in by USB. A clone may need the CH340 driver before Windows shows it at all.'
    }
}

function Get-CaptureResult {
    # Video capture devices land in the Camera class on Windows 10 and 11,
    # webcams and USB grabbers alike. Nothing here can tell one from the
    # other, so they are listed for the reader to recognise rather than
    # guessed at.
    $cameras = @(Get-PnpDevice -Class Camera -PresentOnly -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty FriendlyName)
    if ($cameras.Count -gt 0) {
        return [ordered]@{
            found = $true; verdict = 'ok'; devices = $cameras
            message = "Capture device(s) present: $($cameras -join ', '). Which one is the grabber is for you to say; both a webcam and a USB grabber look like this."
        }
    }
    return [ordered]@{
        found = $false; verdict = 'missing'; devices = @()
        message = 'No video capture device found. Plug the USB grabber in. A UVC grabber needs no driver; some cheap ones want the vendor driver first.'
    }
}

$board = Get-BoardResult
$capture = Get-CaptureResult
$ok = $board.usable -and $capture.found

$result = [ordered]@{
    ok = $ok
    board = $board
    capture = $capture
    # Stated every time: the one piece of the rig nothing can see.
    shieldNote = 'The Video Experimenter shield cannot be detected - it is passive and enumerates nothing. A board being present does not mean the shield is on it.'
}

if ($Json) {
    $result | ConvertTo-Json -Depth 5
} else {
    Write-Output "Arduino : $($board.message)"
    Write-Output "Capture : $($capture.message)"
    Write-Output "Note    : $($result.shieldNote)"
    Write-Output ""
    Write-Output $(if ($ok) { 'Ready: the hardware this needs is plugged in.' }
                   else { 'Not ready: see above. The calibration half of the app works without it.' })
}

exit $(if ($ok) { 0 } else { 1 })
