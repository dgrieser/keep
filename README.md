# keep

A command-line client for Google Keep. List, read, create, edit and delete notes and
checklists, manage labels, pin, archive, color and search — all from the terminal.

It is built on [gkeepapi](https://github.com/kiwiz/gkeepapi), an unofficial client for the
Keep API used by the Android app. It works with personal Google accounts as well as Workspace
accounts, but because the API is unofficial it may break if Google changes it.

## Installation

### Prebuilt binaries

Every tagged release on the [Releases page](https://github.com/dgrieser/keep/releases) ships
self-contained Linux binaries that need no Python installation:

| File | Target |
|------|--------|
| `keep-linux-amd64` | 64-bit x86 Linux |
| `keep-linux-arm64` | 64-bit ARM Linux, e.g. Raspberry Pi 4 / 5 running a 64-bit Raspberry Pi OS |

```sh
# pick amd64 or arm64
ARCH=arm64
curl -fsSLO "https://github.com/dgrieser/keep/releases/latest/download/keep-linux-${ARCH}"
curl -fsSLO "https://github.com/dgrieser/keep/releases/latest/download/keep-linux-${ARCH}.sha256"
sha256sum -c "keep-linux-${ARCH}.sha256"
install -m 0755 "keep-linux-${ARCH}" ~/.local/bin/keep   # or /usr/local/bin/keep
keep --help
```

The binaries are built on Debian bullseye and require glibc 2.31 or newer, which covers
Debian 11+, Ubuntu 20.04+ and Raspberry Pi OS Bullseye or newer. A Raspberry Pi running a
32-bit OS is not covered; use the source install below instead.

### From source

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```sh
# run from a checkout
uv sync
uv run keep --help

# or install the `keep` command globally
uv tool install .
keep --help
```

## Login

Google no longer allows password logins for third-party clients, so the CLI needs a one-time
OAuth token that it exchanges for a long-lived *master token*:

1. Run `keep login`. It asks for your Google account email.
2. Open <https://accounts.google.com/EmbeddedSetup> in a browser (an incognito window is
   easiest), sign in with that account and accept the terms. The page may then spin forever;
   that is expected.
3. In the browser's developer tools open *Application → Cookies → accounts.google.com* and
   copy the value of the cookie named `oauth_token` (it starts with `oauth2_4/`).
4. Paste it into the prompt.

The master token is stored in `~/.config/keep/config.json` (or `$XDG_CONFIG_HOME/keep/`)
with owner-only permissions. Treat it like a password: it grants access to your Google
account. `keep logout` removes it again.

For scripts and CI you can skip the config file and set `KEEP_EMAIL` and `KEEP_MASTER_TOKEN`
in the environment instead. If you already have a master token, `keep login --master-token`
stores it directly.

A local cache of your notes lives in `~/.cache/keep/state.json` so that repeated commands only
need an incremental sync. It is safe to delete at any time.

## Usage

Note IDs can be abbreviated to any unique prefix. All read commands accept `--json`.

```sh
# list notes (archived and trashed are hidden by default)
keep list
keep list --search groceries --label todo --pinned
keep list --archived            # only archived
keep list --all                 # active + archived
keep list --trashed
keep list --color yellow --limit 5 --json

# read one note
keep read 1a096add317
keep read 1a096add317 --json

# create
keep create "Meeting notes" --text "Discuss roadmap" --label work --color blue --pin
echo "multi-line body" | keep create "From stdin" --stdin
keep create "Groceries" -i milk -i eggs --checked bread --label shopping

# edit
keep edit 1a096add317 --title "New title" --append "one more line"
keep edit 1a096add317 --text "replace the whole body"
keep edit 1a096add317 --pin --color green --add-label urgent --remove-label work
keep edit 1a096add317 --archive
keep edit 1a096add317                 # open title + body in $EDITOR

# edit checklists (items by 1-based index or exact text)
keep edit 1a096add317 --check 1 --uncheck eggs --add-item butter --remove-item bread

# delete / restore
keep delete 1a096add317               # moves to trash, asks for confirmation
keep delete 1a096add317 --permanent -y
keep restore 1a096add317

# labels
keep labels list
keep labels create ideas
keep labels delete ideas -y
```

When editing in `$EDITOR`, plain notes are shown as the title, a blank line, then the body.
Checklists are shown as the title, a blank line, then one item per line as `[ ] text` or
`[x] text`; add, remove or reorder lines to change the list.

### Colors

`white`, `red`, `orange`, `yellow`, `green`, `teal`, `blue`, `darkblue`, `purple`, `pink`,
`brown`, `gray`.

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | success |
| 1 | authentication or Google Keep API error, or a declined confirmation |
| 2 | usage error: unknown note, label or checklist item, ambiguous prefix, invalid option combination |

## Development

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pytest
```

The tests run fully offline against an in-memory gkeepapi instance; nothing talks to Google.

### Building a binary locally

```sh
./scripts/build-binary.sh     # needs uv and binutils; writes dist/keep-linux-<arch> + .sha256
```

### Releasing

The version lives in `src/keep_cli/__init__.py`. To publish a release:

```sh
# 1. bump __version__, commit
# 2. tag and push the tag
git tag v0.2.0
git push origin v0.2.0
```

The `Release` GitHub Actions workflow then runs lint and tests, checks that the tag matches
`__version__`, builds the amd64 and arm64 binaries on native runners, and creates a GitHub
release with the binaries, their `.sha256` files and auto-generated release notes attached.
Running the workflow manually from the Actions tab builds the binaries as workflow artifacts
without creating a release.
