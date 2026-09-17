# confluence2obsidian

A small, read-only **Confluence Cloud → Obsidian** exporter/sync tool.

It reads pages and attachments from Confluence Cloud and writes normal Markdown files into an Obsidian vault. It never writes back to Confluence.

## v0.3 highlights

- Preserves the mixed Confluence hierarchy (pages + real Confluence folders used as ancestors).
- Uses the Confluence `position` field to preserve manual sibling ordering.
- Generates a `sorting-spec` compatible with the Obsidian **Custom File Explorer Sorting** community plugin.
- Uses the folder-note convention (`Thoughts/Thoughts.md`) for pages that also have children.
- Generates one space folder note (`Space/Space.md`) that stores the sorting specification. A folder-note plugin can hide this note and make the folder clickable.
- Stores `confluence_position` and `confluence_type` in page frontmatter.
- Cleans up the old generated Markdown file when a synced Confluence page moves to a new path.
- Includes the authenticated attachment-download fix from v0.1.1/v0.2.

## Recommended Obsidian plugins

For a sidebar that looks close to Confluence, install these Community Plugins in Obsidian:

1. **Custom File Explorer Sorting** — reads the generated `sorting-spec` and displays siblings in Confluence order.
2. A folder-note plugin such as **Simple Folder Note** — hides `Folder/Folder.md` duplicates and opens the note when the folder is clicked.

The exporter does not install or modify Obsidian plugins itself.

## Installation

```bash
cd confluence2obsidian-v0.3
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For development/tests:

```bash
pip install -e '.[dev]'
pytest
```

## Authentication

Set your Confluence Cloud base URL, Atlassian email, and API token as environment variables:

```bash
export CONFLUENCE_URL='https://YOUR-DOMAIN.atlassian.net'
export CONFLUENCE_EMAIL='you@example.com'
export CONFLUENCE_API_TOKEN='YOUR_API_TOKEN'
```

Do **not** commit the API token. Credentials are not written into the vault.

## Usage

Check authentication:

```bash
confluence2obsidian spaces
```

Export one page:

```bash
confluence2obsidian page 123456789 --vault ~/Obsidian/TestVault
```

Sync a complete space:

```bash
confluence2obsidian sync --space LAB --vault ~/Obsidian/Lab
```

Personal-space keys beginning with `~` should be quoted in the shell:

```bash
confluence2obsidian sync \
  --space '~71202034f498292f144eda8b842b2a6080ddd9' \
  --vault ~/Obsidian/Lab
```

Skip attachments if desired:

```bash
confluence2obsidian sync --space LAB --vault ~/Obsidian/Lab --no-attachments
```

Force a complete rewrite:

```bash
confluence2obsidian sync --space LAB --vault ~/Obsidian/Lab --force
```

## Hierarchy mapping

A Confluence tree like:

```text
GPCR Immunisation                [Confluence folder]
├── Thoughts                     [page]
│   └── Notes SFB1423 Prof Heitman
├── Wet Lab Plan                 [page]
├── Comp Methods                 [Confluence folder]
│   └── Nanobody                 [page]
└── Writing                      [Confluence folder]
    └── Introduction             [page]
```

becomes:

```text
Space/
├── Space.md                     # generated sorting/folder note
└── GPCR Immunisation/
    ├── Thoughts/
    │   ├── Thoughts.md          # actual Thoughts page
    │   └── Notes SFB1423 Prof Heitman.md
    ├── Wet Lab Plan.md
    ├── Comp Methods/
    │   └── Nanobody.md
    └── Writing/
        └── Introduction.md
```

With a folder-note plugin, `Space.md` and `Thoughts/Thoughts.md` can be hidden from the File Explorer so the visible hierarchy resembles Confluence.

## Preserving Confluence order

Confluence exposes a numeric `position` for content-tree items. v0.3 keeps that value in page metadata and uses it to generate an explicit Custom File Explorer Sorting configuration.

The generated space folder note contains frontmatter resembling:

```yaml
---
confluence_type: space
confluence_space_id: '123'
sorting-spec: |
  target-folder: My Space/GPCR Immunisation
  {:%parent-folder-name%:}
  Thoughts
  Wet Lab Plan
  Delete all but extracellular residues chimerax
  Comp Methods
  Writing
  Notes Medchemcases Prof Gmeiner
  Notes Hossein Batebi
  Structures
  %
---
```

The `%` line means local-only notes or generated attachment folders are retained and displayed after the Confluence-managed items.

After syncing, enable **Custom File Explorer Sorting** and trigger its refresh/sort command. The plugin reads `sorting-spec` entries from folder notes.

## Page metadata

Generated page notes contain metadata such as:

```yaml
---
confluence_id: '123456789'
confluence_type: page
confluence_space_id: '98765'
confluence_version: 17
confluence_position: 42
confluence_parent_id: '123456'
confluence_parent_type: folder
confluence_url: https://example.atlassian.net/wiki/...
tags:
- protein-design
synced_at: '2026-08-24T12:00:00+00:00'
---
```

Sync bookkeeping lives in:

```text
.confluence-sync/state.json
```

## Important limitations

Confluence has many macros and apps. Unknown macros are retained as warning callouts with their textual content rather than silently discarded. Some complex layouts, Jira widgets, databases, whiteboards, comments, inline comments, page properties and app-specific content need dedicated converters.

The current hierarchy is page-oriented: non-page Confluence items are included when they are ancestors of exported pages. Completely empty Confluence folders or standalone whiteboards/databases are not exported yet.

Duplicate page titles are exported safely, but title-only Confluence links can be ambiguous.

This is a read-only exporter with respect to Confluence. It writes files in the chosen Obsidian vault.
