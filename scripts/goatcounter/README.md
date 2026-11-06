# GoatCounter deployment

Deployed and checked on 2026-11-05. These files are the deployed configuration,
not a proposed setup. Site changes remain uncommitted and unpublished.

## Release and host

The current stable [release is v2.7.0](https://github.com/arp242/goatcounter/releases/tag/v2.7.0).
The linux-amd64 gzip was downloaded from that release on the server. Its SHA-256
matched the digest displayed in GitHub's expanded release assets:

```text
98d221cb9c8ef2bf76d8daa9cca647839f8d8b0bb5bc7400ff9337c5da834511  goatcounter-v2.7.0-linux-amd64.gz
goatcounter-v2.7.0-linux-amd64.gz: OK
version=v2.7.0; go=go1.25.5; GOOS=linux; GOARCH=amd64; race=false; cgo=true
```

Verified Ubuntu 24.04, x86_64, with 224 GB free on `/`,
passwordless sudo, existing units, accounts and listeners before installing.
No GoatCounter account, directory or service existed. Ports 8081 and 8444 were
free. Linger was already enabled for the SSH user; it was not changed. All new units
are system units. No existing application, Apache configuration or other user's
files were changed.

## Files and services

`/opt/goatcounter/goatcounter` is the verified binary. The Python scripts and
`privacy.sql` beside it match this directory. The dedicated system account
`goatcounter` has no login shell. `/var/lib/goatcounter` is mode 0700 and holds
`db.sqlite3` on persistent disk. Database and backup files are mode 0600.

The four unit files here are installed in `/etc/systemd/system/`.
`goatcounter.service`, `goatcounter-collection.service` and
`goatcounter-maintenance.timer` are enabled. The serve command is:

```sh
/opt/goatcounter/goatcounter serve -listen 127.0.0.1:8081 -tls none -public-port 8081 -db sqlite+/var/lib/goatcounter/db.sqlite3 -debug=
```

In [handlers/backend.go](https://github.com/arp242/goatcounter/blob/v2.7.0/handlers/backend.go#L59),
HTTP request logging requires debug module `req`. `-debug=` leaves it off.
Both serving units also use `StandardOutput=null` and `StandardError=null`,
because error reports can contain hit fields. The proxy's `log_message` is a
no-op. The journal retains systemd service status, not HTTP request lines.
The maintenance unit prints only retention, expiry and integrity status.

The dedicated Python proxy listens on `127.0.0.1:8444`. It forwards GET or POST
only at exact `/count`, strips unapproved fields and headers, and returns 404
for the dashboard, API, assets and other paths. It does not forward client IPs,
cookies, Referer or language headers. UA reaches GoatCounter only for its bot
filter. DNT/GPC headers are also honored here. Poster review paths are rejected.
There is no separate pixel route or locally loaded vendor script.

Tailscale's self DNS name was verified against the public collection URL below.
Although reading Tailscale state worked without sudo, changing Funnel required sudo:

```sh
sudo tailscale funnel --bg --https=8443 http://127.0.0.1:8444
```

Public collection URL: `https://devvm.tail77ab30.ts.net:8443/count`.
HTTPS terminates in Funnel. Its stored background configuration survives reboot.
`tailscale funnel status` reports only this collection proxy. To turn it off,
use `sudo tailscale funnel --https=8443 off`.

The dashboard is available only through an SSH forward:

```sh
ssh -F /dev/null -N -L 8081:127.0.0.1:8081 "$COUNTER_SSH"
# Open http://stats.localhost:8081/
```

The reserved admin login and its generated password are in
`/etc/goatcounter/admin-credentials`, root-readable only; retrieve them with
sudo on the server. No real email address or public API token was created.

## Property and privacy settings

One property, site ID 1, serves public documents and AI Tells. It was created
with the following CLI arguments, with a generated password passed by a Python
subprocess and saved in the root-only credentials file:

```sh
sudo -u goatcounter /opt/goatcounter/goatcounter db create site -createdb -db sqlite+/var/lib/goatcounter/db.sqlite3 -vhost stats.localhost -user.email "$gc_login" -user.password "$gc_password"
```

The CLI does not expose the collection settings. Python's standard `sqlite3`
module applied `/opt/goatcounter/privacy.sql` before the service accepted counts:

```python
with sqlite3.connect('/var/lib/goatcounter/db.sqlite3') as db:
    db.executescript(Path('/opt/goatcounter/privacy.sql').read_text())
```

`sqlite3` CLI is absent on the server; database checks use Python's SQLite module.
[settings.go](https://github.com/arp242/goatcounter/blob/v2.7.0/settings.go#L29)
defines the verified bitmask: 1 nothing, 2 referrer, 4 UA, 8 screen, 16 location,
32 location region, 64 language, 128 session, 256 individual hits. The configured
value is **2**, retention is **0 (indefinite — owner decision 2026-11-05; GoatCounter's own cron skips deletion at 0)**, `public` is **private**, and `secret` is empty.
Public visitor counters, sharing and embeds are disabled.

Two upstream behaviours require the SQL guards, even with collect=2.
[memstore.go](https://github.com/arp242/goatcounter/blob/v2.7.0/memstore.go)
inserts bot rows before checking collection flags and serializes even empty
session maps at shutdown. Triggers discard inserts into `bots`, `hits` and the
`store` key `session`. Session generation itself is disabled by collect=2.
Do not remove these guards when upgrading; recheck source and behaviour first.

The browser reporter uses POST `/count` with **URL query parameters**, as
[handlers/count.go](https://github.com/arp242/goatcounter/blob/v2.7.0/handlers/count.go)
requires: `p` is the page or event, `e=true` marks an event, `r` is a referrer
origin, and `q=ref=label` carries a validated shared-link label. The release
removes `ref` from page paths and reads it from `q` as a referral label, so the
reporter deliberately sends the bare canonical path in `p`. No title, random
identifier, size, browser language or quiz result is sent.

## Retention and backups

**The statistics are kept indefinitely** (owner decision 2026-11-05): the
site setting is `data_retention=0`, which GoatCounter's own retention cron
skips (`cron/tasks.go`: `if s.Settings.DataRetention <= 0 { continue }`),
and `maintenance.py` performs no deletion. Nothing in the deployment removes
collected aggregates automatically; to remove data, delete rows or the whole
site via the dashboard/CLI.

The enabled `goatcounter-maintenance.timer` runs at **03:20 UTC daily**
(`Persistent=true` to catch a missed run):

```sh
/usr/bin/python3 /opt/goatcounter/maintenance.py
```

The script vacuums the database, checkpoints the WAL, then uses SQLite's
online backup API to create `/var/lib/goatcounter/backups/YYYY-MM-DD.sqlite3`.
It checks integrity, replaces that day's backup atomically, and deletes backup
dates at least 7 days old (the primary database is unaffected). The backups
are on the same server, not a separate disaster-recovery copy.

The job was run successfully after the policy change. Its exact summary was:

```text
maintenance: retention=indefinite; backup integrity=ok; backup expiry=7 days
```

Scratch-database checks exercised expired/current aggregates (both must
survive), seven-day backup deletion, snapshot integrity, SQL guards and proxy
filtering:

```sh
/opt/goatcounter/goatcounter db schema-sqlite > schema.sql
python3 scripts/goatcounter/checks.py schema.sql
```

The first command ran on the server and its schema was used by the local check.
For a graceful restart, use `sudo systemctl restart goatcounter.service`.
`PartOf=goatcounter.service` restarts the collection proxy with it. Both units
were confirmed active after this command.

## Publication checks and remaining owner work

The site build succeeds and the leak scan is clean. The scan has one explicit
exception for the exact public collection URL, including in source and docs;
other tailnet hosts and private IPs still fail. The build emits 12
pre-existing pandoc warnings while extracting plain-text section metadata.
The same warnings were reproduced byte-for-byte from the HEAD source with the
old metadata template. They do not arise in the HTML rendering step.

The privacy page deliberately retains marked English and Czech contact
placeholders. The owner supplies them before publication. A request forced
through public Funnel ingress returned 200; the owner should still check the
URL on a phone with Tailscale off. No page or event requests are sent when the
browser sets a DNT or GPC signal. Only synthetic acceptance
traffic has been sent. Seven synthetic counts remain, including one event.
