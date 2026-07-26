# AGENTS.md — Solo Qt GUI Python Projects

This repository is maintained by one developer with AI assistance.
Optimize for clarity, safe refactoring, and a GUI that stays responsive.

## Project type

- Python desktop GUI app using **PySide6** (Qt 6).
- Solo project: no team processes, but keep structure so humans and agents can navigate the code later.

## Naming conventions (required)

| Item | Style | Example |
|------|-------|---------|
| Source file names | camelCase | `mainWindow.py`, `exportCsvDialog.py` |
| Variables, functions, methods | camelCase | `userName`, `loadSettings()`, `onSaveClicked()` |
| Widget object names | camelCase | `statusLabel`, `openButton`, `filePathEdit` |
| Classes | PascalCase | `MainWindow`, `SettingsService` |
| Constants | camelCase or UPPER_SNAKE | Prefer `maxRecentFiles`; UPPER_SNAKE only for true constants |
| User-visible UI text | Title Case with spaces | `"Open File"`, `"Settings"` (not camelCase in labels users read) |

Do **not** use snake_case for new files or identifiers in this project unless required by a third-party API.

## Architecture (mandatory separation)

| Layer | Location | Allowed | Forbidden |
|-------|----------|---------|-----------|
| Entry | `src/<app>/main.py` | Start `QApplication`, load config, show main window | Business logic, heavy work |
| UI | `src/<app>/ui/` | Widgets, layouts, signals wired to slots | Database calls, file parsing, long loops |
| Services | `src/<app>/services/` | Business rules, I/O, calculations | `QWidget`, `QDialog` imports |
| Models | `src/<app>/models/` | Dataclasses, enums, plain state | Qt widgets |
| Config | `appConfig.py` | Paths, defaults, env/settings load | Feature logic |

**Rule of thumb:** If it does not draw pixels or handle input, it does not belong in `ui/`.

## File size and structure

- Target **≤ 500 lines per file**; split by feature when larger.
- One primary window or dialog per file under `ui/`.
- Methods: prefer **≤ 50 lines**; split when there are distinct steps or branches.
- New features go in a **feature folder** under `services/` and `ui/`, not appended to `mainWindow.py`.

Example for an export CSV feature:

```text
services/exportCsvService.py
ui/dialogs/exportCsvDialog.py
tests/testServices/testExportCsvService.py
```

## Qt GUI rules

1. **Never block the GUI thread.** Use `QThread` + signals, or `QThreadPool` + `QRunnable`, for file I/O, network, and heavy computation.
2. **Main window stays thin.** It composes widgets and connects signals; logic lives in services.
3. **Prefer typed signals** where practical (`Signal(str)`, not bare `Signal()`).
4. **User-facing strings** live in UI layer or `appConfig.py` constants—not scattered magic strings.
5. **Resources** (icons, `.ui`, `.qss`) go in `resources/`; paths defined in `appConfig.py`.

## Python standards

- Python **3.14+**.
- **Type hints** on all public functions and methods.
- **`pyproject.toml`** for dependencies and tooling (ruff, pytest).
- Use **dataclasses** or small classes for structured data—not dict soup.
- Logging via `logging` module; no bare `print()` in library/service code (OK in `main.py` for dev).

## Dependencies

- GUI: `PySide6`
- Testing: `pytest`, `pytest-qt`
- Lint/format: `ruff`

Add new dependencies only when needed; update `pyproject.toml`.

## Testing expectations

- **Services:** unit tests required for non-trivial logic.
- **UI:** smoke tests with `pytest-qt` (window opens, buttons exist, critical paths).
- Do not require 100% coverage; do require tests for bugs once fixed.

## When adding or changing behavior

1. Read `README.md` and this file first.
2. Identify the layer (ui / services / models)—put code in the right folder.
3. If touching UI + logic, implement **service first**, then wire UI.
4. If a file exceeds ~500 lines, **split before** adding more code.
5. Update `README.md` if user-visible flow changes.

## What not to do

- Do not create a single monolithic module with everything inside.
- Do not put SQL, HTTP, or file parsing inside widget classes.
- Do not use `time.sleep()` or long synchronous work on the GUI thread.
- Do not introduce new frameworks unless explicitly requested.
- Do not commit secrets, API keys, or `.env` with real credentials.
- Do not rename files or symbols to snake_case during refactors.

## Refactoring

When the app works but code is messy:

1. Extract services from widgets without changing behavior.
2. Add minimal tests around extracted logic.
3. Split oversized files by feature.
4. Update `README.md` architecture section.
