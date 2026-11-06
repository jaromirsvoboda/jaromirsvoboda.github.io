#!/usr/bin/python3
"""Daily maintenance: vacuum the database and make a consistent backup.

No deletion: per owner decision (2026-11-05) the statistics are kept
indefinitely (site data_retention=0; GoatCounter cron skips deletion at
0). Backups still rotate on a 7-day window; the primary database is the
permanent record.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sqlite3

STATE = Path("/var/lib/goatcounter")


def maintain(state=STATE, now=None):
    now = now or datetime.now(timezone.utc)
    backups = state / "backups"
    backups.mkdir(mode=0o700, exist_ok=True)
    db = sqlite3.connect(state / "db.sqlite3", timeout=30)
    with db:
        db.execute("VACUUM")
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    target = backups / (now.strftime("%Y-%m-%d") + ".sqlite3")
    temporary = target.with_suffix(".tmp")
    with sqlite3.connect(temporary) as output:
        db.backup(output)
        assert output.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    db.close()
    os.chmod(temporary, 0o600)
    temporary.replace(target)
    for backup in backups.glob("*.sqlite3"):
        day = datetime.strptime(backup.stem, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if day.date() <= (now - timedelta(days=7)).date():
            backup.unlink()
    print("maintenance: retention=indefinite; backup integrity=ok; backup expiry=7 days")


if __name__ == "__main__":
    os.umask(0o077)
    maintain()
