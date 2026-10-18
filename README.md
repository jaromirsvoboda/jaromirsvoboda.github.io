# jaromirsvoboda.github.io

Things I publish: demonstrations, tutorials, summaries and lists, most of them
written with LLMs (Claude and others) and reviewed by me. Served at
<https://jaromirsvoboda.github.io/>.

## How it works

- `site/` holds the published files. Markdown and Jupyter notebooks are rendered
  to HTML by [pandoc](https://pandoc.org) at build time; everything else is served
  as is.
- `scripts/publish <source> [<path under site/>]` copies a file or folder in,
  commits and pushes it. GitHub Actions (`.github/workflows/deploy.yml`) then
  builds and deploys the site.
- `scripts/build [<out dir>]` builds the site locally (default `_site/`).

Needs python3 and gitleaks; local builds also need pandoc (CI pins pandoc 3.11 and
gitleaks 8.30.1; use the same versions locally).

## Library

`site/library/<slug>/` holds one longer document per folder: `index.md` (the page, with
front matter: `title`, `date`, `summary`, `license`, `downloads`, `show-toc`), `figures/`,
and `download/` (EPUB, A4 PDF, Markdown source; files under `download/` are served as is,
never rendered). `scripts/build` generates `library/index.html` from the front matter,
newest first. From an Obsidian note in the vault, the folder is made by
`scripts/note-to-site.py` (in the vault) and published with
`scripts/publish <folder> library/<slug>`.

Pages use `scripts/template.html` (light and dark themes, download box, licence footer).

## Leak scan

Anything pushed here stays in public history, so content is scanned before it
enters the repo, not only before it is deployed:

1. `scripts/publish` scans the source before copying it.
2. The `pre-push` hook scans all of `site/` (enable once per clone with
   `git config core.hooksPath .githooks`).
3. The deploy workflow scans again and refuses to deploy on a finding.

`scripts/leak-scan` checks generic patterns (`scripts/leak-patterns`: private and
Tailscale addresses, home paths, e-mail addresses), a private list of names kept
outside this repo, and credentials via [gitleaks](https://github.com/gitleaks/gitleaks).
