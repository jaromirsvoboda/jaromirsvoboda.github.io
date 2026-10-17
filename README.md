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
