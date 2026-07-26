"""Application configuration — paths, defaults, and metadata."""

from __future__ import annotations

from pathlib import Path

appName = "RV Backup Helper"
appVersion = "0.1.0"
organizationName = "Charette AI Group"

# Help > About contents
editorName = "Francois Charette"
aiAgentName = "Claude - Fable 5"
copyrightHolder = "Charette AI Group, LLC"

projectRoot = Path(__file__).resolve().parents[2]
resourcesDir = Path(__file__).resolve().parent / "resources"
windowTitle = appName
defaultWindowWidth = 800
defaultWindowHeight = 600
