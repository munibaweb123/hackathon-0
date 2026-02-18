---
name: filesystem-watcher
description: Monitors a drop folder for new files using watchdog and creates markdown action files in the Obsidian vault with file attachments.
---

# Filesystem Watcher Agent Skill

Monitors a designated **drop folder** for new files using watchdog (event-driven, instant detection) and creates action files in the Obsidian vault's `Needs_Action/` folder.

## Quick Start

### With UV (recommended)

```bash
# Create your drop folder
mkdir -p ~/AI_Employee/Drop

# Start monitoring
uv run filesystem_watcher.py --drop-folder ~/AI_Employee/Drop
```

### With pip

```bash
pip install -r requirements.txt
python filesystem_watcher.py --drop-folder ~/AI_Employee/Drop
```

### Process existing files only (no live monitoring)

```bash
uv run filesystem_watcher.py --once --drop-folder ~/AI_Employee/Drop
```

## How It Works

1. **Drop a file** into `~/AI_Employee/Drop/` (or your configured folder)
2. Watchdog **triggers instantly** (no polling delay)
3. File is **copied** to `vault/Attachments/`
4. A **markdown action file** is created in `vault/Needs_Action/`
5. The **source file is cleaned up** from the drop folder

## Architecture

```
Drop Folder (watchdog)
       │
       ▼  on_created event
  FilesystemWatcher.handle_new_file()
       │
       ├──▶ Attachments/{filename}              (file copy)
       ├──▶ Needs_Action/FILE_{filename}.md     (action file)
       ├──▶ Logs/filesystem_watcher.log          (rotating log)
       └──▶ Logs/processed_ids.json              (dedup state)
       │
       ▼
  Source file deleted from drop folder
```

## Supported File Types

| Type | Extensions |
|------|-----------|
| Documents | `.pdf`, `.docx`, `.doc`, `.xlsx`, `.xls`, `.pptx`, `.txt`, `.csv`, `.md` |
| Images | `.png`, `.jpg`, `.jpeg`, `.gif`, `.svg`, `.webp` |
| Archives | `.zip`, `.tar`, `.gz` |
| Other | Any file with a recognized MIME type |

## Ignored Files

The watcher automatically skips:
- Hidden files (starting with `.`)
- Temp files (starting with `~` or `__`)
- Partial downloads (`.tmp`, `.swp`, `.part`, `.crdownload`, `.lock`)
- Zero-byte files
- Files exceeding the size limit (default: 100 MB)

## Output Format

Each file produces an action file like `Needs_Action/FILE_report.pdf.md`:

```markdown
---
type: file
original_name: "report.pdf"
size: "2.4 MB"
mime_type: application/pdf
created_at: 2026-02-15T10:30:00+00:00
status: needs_action
---

## New File: report.pdf

**Size:** 2.4 MB
**Type:** application/pdf
**Extension:** .pdf
**Received:** 2026-02-15 10:30 AM UTC
**Attachment:** [[Attachments/report.pdf]]

### Suggested Actions

- [ ] Review this file
- [ ] Forward to team
- [ ] Archive
- [ ] Delete
```

The `[[Attachments/report.pdf]]` link is an Obsidian wikilink — clicking it opens the file directly in Obsidian.

## Duplicate Handling

- **Attachments**: If `report.pdf` already exists, the copy is saved as `report_1.pdf`, `report_2.pdf`, etc.
- **Action files**: Same pattern — `FILE_report.pdf_1.md`, `FILE_report.pdf_2.md`
- **Dedup tracking**: `processed_ids.json` prevents reprocessing the same filename

## Configuration

| Variable | CLI Flag | Default |
|----------|----------|---------|
| `VAULT_PATH` | `--vault-path` | `./obsidian-vault` |
| `DROP_FOLDER` | `--drop-folder` | `~/AI_Employee/Drop` |
| — | `--max-size` | `100` (MB) |
| — | `--once` | Process existing files and exit |

## CLI Options

```
usage: filesystem_watcher.py [-h] [--vault-path PATH] [--drop-folder PATH]
                             [--max-size MB] [--once]

--vault-path    Path to the Obsidian vault
--drop-folder   Folder to monitor for new files
--max-size      Maximum file size in MB (default: 100)
--once          Process existing files and exit (no live monitoring)
```

## File Structure

```
.claude/skills/filesystem-watcher/
├── SKILL.md               # This documentation
├── filesystem_watcher.py  # Main UV-runnable script (watchdog)
├── file_handler.py        # File validation, MIME detection, copy, cleanup
└── requirements.txt       # Dependencies
```

Uses `base_watcher.py` from the sibling `gmail-watcher` skill for logging and deduplication.

## Key Differences from Other Watchers

| | Gmail Watcher | WhatsApp Watcher | Filesystem Watcher |
|---|---|---|---|
| Detection | Polling (2 min) | Polling (30s) | **Event-driven (instant)** |
| Library | Google API | Playwright | **watchdog** |
| Input | Gmail API | WhatsApp Web | **Local filesystem** |
| No auth needed | OAuth2 | QR code | **None** |
