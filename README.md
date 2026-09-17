# confluence2obsidian

A read-only **Confluence Cloud → Obsidian** exporter and sync tool.

It reads pages, hierarchy information, and attachments from Confluence Cloud and writes normal Markdown files into an Obsidian vault. It never writes back to Confluence.

## What it does

- Export a single Confluence page to Markdown.
- Sync an entire Confluence space.
- Preserve page hierarchy and real Confluence folders.
- Download page attachments.
- Convert common Confluence formatting and macros to Markdown.
- Convert internal Confluence links to Obsidian links where possible.
- Preserve Confluence page ordering.
- Store Confluence IDs and versions in YAML frontmatter.
- Skip unchanged pages on later syncs.
- Never delete unrelated/local notes from the vault.

## Before you start

You need:

- A Confluence Cloud account with access to the pages you want to copy.
- An Atlassian API token.
- Python 3.10 or newer.
- An Obsidian vault, or an empty folder you want to use as a vault.

The examples below use `/path/to/vault` as the Obsidian vault location. Replace it with the real path to your own vault.

---

# Installation

## 1. Download the project

Download and unzip the project, then open a terminal inside the project folder.

For example:

```bash
cd /path/to/confluence2obsidian-v0.3
```

If you are not sure where you are, run:

```bash
pwd
```

## 2. Check that Python is installed

Run:

```bash
python3 --version
```

You need Python 3.10 or newer.

On Ubuntu, if Python or the virtual-environment package is missing:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

## 3. Create a virtual environment

Inside the project folder, run:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Your terminal should now begin with something like:

```text
(.venv) user@computer:...
```

Whenever you open a new terminal later, return to the project folder and activate the environment again:

```bash
cd /path/to/confluence2obsidian-v0.3
source .venv/bin/activate
```

## 4. Install confluence2obsidian

Run:

```bash
pip install -e .
```

Check the installation:

```bash
confluence2obsidian version
```

For this release, the output should be:

```text
0.3.0
```

For development and tests, install the optional development dependencies:

```bash
pip install -e '.[dev]'
pytest
```

---

# Connecting to Confluence

## 5. Create an Atlassian API token

Open your Atlassian account security settings and create an API token.

For this version, use a regular API token rather than a scoped token.

Give it a recognizable name such as:

```text
Confluence2Obsidian
```

Copy the token when Atlassian shows it.

Treat the token like a password. Do not put it in this repository, in the README, or in a GitHub commit.

## 6. Find your Confluence base URL

If a normal Confluence page has a URL such as:

```text
https://your-company.atlassian.net/wiki/spaces/SPACE/pages/123456789/title_of_your_page
```

then your base URL is:

```text
https://your-company.atlassian.net
```

Do not include `/wiki`.

## 7. Set your credentials

For a quick test, run:

```bash
export CONFLUENCE_URL='https://your-company.atlassian.net'
export CONFLUENCE_EMAIL='you@example.com'
export CONFLUENCE_API_TOKEN='YOUR_API_TOKEN'
```

These variables disappear when you close the terminal.

### Optional: store credentials outside the project

Create a private configuration directory:

```bash
mkdir -p ~/.config/confluence2obsidian
```

Create a credentials file:

```bash
nano ~/.config/confluence2obsidian/credentials.sh
```

Add:

```bash
export CONFLUENCE_URL='https://your-company.atlassian.net'
export CONFLUENCE_EMAIL='you@example.com'
export CONFLUENCE_API_TOKEN='YOUR_API_TOKEN'
```

Save the file, then restrict its permissions:

```bash
chmod 600 ~/.config/confluence2obsidian/credentials.sh
```

Before using the tool in a new terminal, load the credentials with:

```bash
source ~/.config/confluence2obsidian/credentials.sh
```

A typical new terminal session therefore looks like:

```bash
cd /path/to/confluence2obsidian-v0.3
source .venv/bin/activate
source ~/.config/confluence2obsidian/credentials.sh
```

---

# Test the connection

## 8. List the Confluence spaces you can access

Run:

```bash
confluence2obsidian spaces
```

You may see output resembling:

```text
SPACE_KEY       1234567       Example Space
ANOTHER_SPACE   7654321       Another Space
~PERSONAL_KEY   2468101       Personal Space
```

The columns are:

```text
SPACE KEY       INTERNAL ID       SPACE NAME
```

Use the **first column** with the `--space` option.

Personal-space keys often start with `~`. Put those keys inside quotation marks when using them in a shell command.

---

# Export one page

## 9. Find the page ID

A Confluence page URL may look like:

```text
https://your-company.atlassian.net/wiki/spaces/SPACE/pages/123456789/title_of_your_page
```

The page ID is:

```text
123456789
```

## 10. Export the page

Run:

```bash
confluence2obsidian page 123456789 \
  --vault /path/to/vault
```

A successful export may print:

```text
updated: title_of_your_page.md
```

For a single-page export, the note is written directly to the chosen vault.

---

# Sync an entire Confluence space

## 11. Sync a normal space

Use the space key from the first column of `confluence2obsidian spaces`:

```bash
confluence2obsidian sync \
  --space YOUR_SPACE_KEY \
  --vault /path/to/vault
```

## 12. Sync a personal space

If the space key starts with `~`, quote it:

```bash
confluence2obsidian sync \
  --space '~YOUR_PERSONAL_SPACE_KEY' \
  --vault /path/to/vault
```

The quotation marks prevent the shell from interpreting `~` as a home-directory shortcut.

## 13. Run the same command again to update the vault

There is no separate update command. Run the same sync command again:

```bash
confluence2obsidian sync \
  --space YOUR_SPACE_KEY \
  --vault /path/to/vault
```

The exporter stores the Confluence version of each generated page and can skip pages that have not changed.

Sync bookkeeping is stored inside the vault at:

```text
.confluence-sync/state.json
```

Normally, you should not edit that file manually.

## 14. Force every page to be regenerated

Use `--force`:

```bash
confluence2obsidian sync \
  --space YOUR_SPACE_KEY \
  --vault /path/to/vault \
  --force
```

## 15. Sync without downloading attachments

Use `--no-attachments`:

```bash
confluence2obsidian sync \
  --space YOUR_SPACE_KEY \
  --vault /path/to/vault \
  --no-attachments
```

Attachments are downloaded by default.

---

# How Confluence hierarchy is represented

Confluence allows a page to contain text and also have child pages. A normal filesystem cannot put files "inside" a Markdown file, so pages with children are represented as folder notes.

For example, this Confluence structure:

```text
folder_name                     [Confluence folder]
├── parent_page                 [page]
│   └── child_page              [page]
├── another_page                [page]
├── methods                     [Confluence folder]
│   └── method_page             [page]
└── writing                     [Confluence folder]
    └── introduction            [page]
```

becomes:

```text
Example Space/
├── Example Space.md
└── folder_name/
    ├── parent_page/
    │   ├── parent_page.md
    │   └── child_page.md
    ├── another_page.md
    ├── methods/
    │   └── method_page.md
    └── writing/
        └── introduction.md
```

`parent_page/parent_page.md` is the actual content of the Confluence page. The surrounding folder exists because that page also has children.

---

# Recommended Obsidian plugins

For an Obsidian sidebar that more closely resembles the Confluence tree, two community plugins are recommended.

## Simple Folder Note

In Obsidian, go to:

```text
Settings → Community plugins → Browse
```

Search for:

```text
Simple Folder Note
```

Install and enable it.

This plugin understands layouts such as:

```text
parent_page/
├── parent_page.md
└── child_page.md
```

and can make the folder itself behave like the page note.

## Custom File Explorer Sorting

Again go to:

```text
Settings → Community plugins → Browse
```

Search for:

```text
Custom File Explorer sorting
```

Install and enable it.

Confluence allows pages and folders to be manually ordered. Normal filesystem views usually sort alphabetically. confluence2obsidian preserves the Confluence position and generates a `sorting-spec` so this plugin can reproduce the Confluence order in Obsidian.

A generated sorting configuration may resemble:

```yaml
---
confluence_type: space
confluence_space_id: '123456'
sorting-spec: |
  target-folder: Example Space/folder_name
  {:%parent-folder-name%:}
  parent_page
  another_page
  methods
  writing
  final_page
  %
---
```

The `%` line allows local-only files or generated attachment folders to appear after the Confluence-managed items.

---

# Generated page metadata

Generated Markdown files contain YAML frontmatter such as:

```yaml
---
confluence_id: '123456789'
confluence_type: page
confluence_space_id: '98765'
confluence_version: 17
confluence_position: 42
confluence_parent_id: '123456'
confluence_parent_type: folder
confluence_url: https://your-company.atlassian.net/wiki/...
tags:
- example-tag
synced_at: '2026-01-01T12:00:00+00:00'
---
```

This information allows the exporter to identify the original Confluence page on later syncs.

---

# Troubleshooting

## `confluence2obsidian: command not found`

The virtual environment may not be active.

Run:

```bash
cd /path/to/confluence2obsidian-v0.3
source .venv/bin/activate
```

Then check:

```bash
confluence2obsidian version
```

## Missing environment variable

Load the credentials file:

```bash
source ~/.config/confluence2obsidian/credentials.sh
```

Then try:

```bash
confluence2obsidian spaces
```

## `401 Unauthorized`

Check the following values:

```text
CONFLUENCE_URL
CONFLUENCE_EMAIL
CONFLUENCE_API_TOKEN
```

The base URL should look like:

```text
https://your-company.atlassian.net
```

not:

```text
https://your-company.atlassian.net/wiki
```

## The hierarchy looks correct but the order is alphabetical

Install and enable **Custom File Explorer sorting**, then refresh/reapply its sorting configuration.

## A folder contains a Markdown file with the same name

For example:

```text
parent_page/
└── parent_page.md
```

This is intentional. Install **Simple Folder Note** to make this folder-note convention behave naturally in Obsidian.

---

# Important limitations

Confluence has many macros, apps, and content types. Unknown macros are retained as warning callouts with their textual content rather than silently discarded.

Some complex layouts, Jira widgets, databases, whiteboards, comments, inline comments, page properties, and app-specific content may require dedicated converters.

The current hierarchy export is page-oriented. Non-page Confluence items are included when they are ancestors of exported pages. Completely empty Confluence folders and standalone whiteboards or databases are not exported yet.

Duplicate page titles are exported safely, but title-only Confluence links can sometimes be ambiguous.

The tool is read-only with respect to Confluence, but it does write and update generated files inside the chosen Obsidian vault.

If you manually edit a generated note, a later sync may overwrite those local changes if the corresponding Confluence page has changed. Keep local-only notes separate from Confluence-managed notes when possible.

---

# Putting the project on GitHub

The following steps are for people who have not used Git or GitHub before.

## 1. Make sure no credentials are inside the project

Do not store an API token in the repository.

Check the files Git will see before uploading anything:

```bash
git status
```

The project `.gitignore` excludes common local files such as `.venv/`, Python caches, and `.env`.

If credentials were stored using the recommended `~/.config/confluence2obsidian/credentials.sh` path, they are outside the repository and will not be uploaded.

## 2. Install Git

Check whether Git is installed:

```bash
git --version
```

On Ubuntu, install it with:

```bash
sudo apt update
sudo apt install git
```

## 3. Configure your Git identity

Run once on your computer:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Check the values:

```bash
git config --global user.name
git config --global user.email
```

## 4. Initialize the repository

Inside the project folder:

```bash
cd /path/to/confluence2obsidian-v0.3
git init
git branch -M main
```

Check what Git sees:

```bash
git status
```

## 5. Create the first commit

Add the project files:

```bash
git add .
```

Check them one more time:

```bash
git status
```

Create the first commit:

```bash
git commit -m "Initial release"
```

## 6. Install GitHub CLI

Check whether it is installed:

```bash
gh --version
```

On Ubuntu, it may be available through:

```bash
sudo apt update
sudo apt install gh
```

## 7. Log in to GitHub

Run:

```bash
gh auth login
```

Choose GitHub.com, HTTPS, and browser login when prompted.

Verify the login:

```bash
gh auth status
```

## 8. Create and upload a public GitHub repository

From inside the project folder:

```bash
gh repo create confluence2obsidian \
  --public \
  --source=. \
  --remote=origin \
  --push
```

To create a private repository instead, replace `--public` with `--private`.

## 9. Open the repository in your browser

Run:

```bash
gh repo view --web
```

## 10. Upload future changes

After editing the project:

```bash
git status
git add .
git commit -m "Describe the change"
git push
```

The basic workflow is:

```text
edit files
    ↓
git add .
    ↓
git commit
    ↓
git push
    ↓
GitHub is updated
```

## Security warning

Never upload an Atlassian API token to GitHub.

If a real API token is accidentally committed or pushed, revoke it in Atlassian immediately and create a new token. Deleting it from only the newest version of a file is not enough because Git preserves older commits.

---

# License

See `LICENSE`.
