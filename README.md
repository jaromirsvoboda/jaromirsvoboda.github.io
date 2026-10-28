# jaromirsvoboda.github.io

Things I publish: demonstrations, tutorials, summaries and lists, most of them
written with LLMs (Claude and others) and reviewed by me. Served at
<https://jaromirsvoboda.github.io/>.

## How it works

- `site/` holds the published files. Markdown and Jupyter notebooks are rendered
  to HTML by [pandoc](https://pandoc.org) at build time; everything else is served
  as is.
- `scripts/publish <source> [<path under site/>]` passes a file or folder through
  the leak gate, copies it in, commits and pushes it. GitHub Actions
  (`.github/workflows/deploy.yml`) then builds and deploys the site.
- `scripts/build [<out dir>]` builds the site locally (default `_site/`).

Needs python3 with Pillow, poppler-utils (`pdftotext`, `pdfinfo`, `pdfdetach`), gitleaks and
access to the owner's local qwen model (see Leak gate); local builds also need pandoc (CI pins pandoc 3.11 and
gitleaks 8.30.1; use the same versions locally).

## Library

`site/library/<slug>/` holds one longer document per folder: `index.md` (the page, with
front matter: `title`, `date`, `summary`, `license`, `downloads`, `show-toc`), `figures/`,
and `download/` (EPUB, A4 PDF, Markdown source; files under `download/` are served as is,
never rendered). `scripts/build` generates `library/index.html` from the front matter,
newest first. From an Obsidian note in the vault, the folder is made by
`scripts/note-to-site.py` (in the vault) and published with
`scripts/publish <folder> library/<slug>`.

## Explainers

`site/explainers/<slug>/` holds one explainer per folder: a page that works through a source
(a book, a paper, a concept) with examples and adds what the source leaves out. One explainer
per source, growing as reading continues. Same folder layout and downloads as the Library, plus
a `source` front-matter entry (`title`, `author`, `url`, `note`) shown under the title; a source
whose licence allows it is rehosted in `download/`. Made with
`scripts/note-to-site.py --section explainers` and published with
`scripts/publish <folder> explainers/<slug>`. `scripts/build` generates `explainers/index.html`
the same way as the Library index. See `GLOSSARY.md` for the terms.

Pages use `scripts/template.html` (light and dark themes, download box, licence footer).

## Leak gate

Anything pushed here stays in public history, and the vault it comes from also holds private
notes. So content passes a gate before it enters the repo, not only before it is deployed.
The gate has four parts:

1. `scripts/strip-metadata` removes EXIF, GPS, PNG text chunks and comments from images.
2. `scripts/leak-scan` matches generic patterns (`scripts/leak-patterns`: private and Tailscale
   addresses, home paths, e-mail addresses) and a private list of names kept outside this repo
   against every file name and every piece of text a reader could reach: the text inside EPUBs
   and PDFs, PDF metadata and image metadata included (`scripts/gatelib.py`). It refuses images
   with a GPS position, and files it cannot read. Then gitleaks looks for credentials.
3. `scripts/semantic-review` has the owner's local qwen model (the text never leaves his own
   hardware; its URL and key live in local config, see the script) read
   the text, the file names and the images and flag personal or confidential content no pattern
   can know about: health, family, finances, work and clients, private people, locations,
   credentials, diary-like notes. Paragraphs found clean are remembered by hash in
   `~/.cache/leak-gate/`, so only new text is read. It fails closed: a finding, or qwen being
   unreachable, stops the publish.
4. `scripts/check-clone` refuses to publish or build unless the pre-push hook is enabled and
   commits use the GitHub noreply address.

They run at three points:

- `scripts/publish` runs 1–3 on a scratch copy before anything enters `site/`.
- The `pre-push` hook checks everything the push would make public, not only the net change
  at the tip (a file added and deleted again still stays in history): every new commit's
  noreply author and committer, its names and message through the pattern scan, and every new
  file version in those commits through the pattern scan and the semantic review. Only branches
  may be pushed. Then it pattern-scans all of `site/`.
- The deploy workflow pattern-scans again and refuses to deploy on a finding (CI cannot reach
  qwen, so the semantic review is local only). GitHub's push protection blocks credentials
  server-side.

Set up each clone once:

```sh
git config core.hooksPath .githooks
git config user.email 8951129+jaromirsvoboda@users.noreply.github.com
```

**When the semantic review flags something**, it prints the findings and the path of a report.
Fix the source. If every finding is a false alarm, the owner (and only the owner, never an agent)
re-runs with `scripts/publish --accept-review <report> ...`, or `LEAK_GATE_ACCEPT=<report> git push`.
Acceptance covers exactly the text reviewed in that report; changed text is reviewed again.

The gate guards against accidents, not against someone determined to bypass it: a clone
without the hook, or `git push --no-verify`, skips the local checks.
