#!/usr/bin/python3
"""Exercise privacy guards, indefinite retention and backup integrity on a scratch database."""
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
from urllib.parse import parse_qs, urlsplit

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


with tempfile.TemporaryDirectory() as scratch:
    state = Path(scratch)
    db = sqlite3.connect(state / "db.sqlite3")
    db.executescript(Path(sys.argv[1]).read_text())
    db.executescript((ROOT / "privacy.sql").read_text())
    db.execute("INSERT INTO store VALUES ('session', '{\"sessions\":{\"visitor\":1}}')")
    db.execute("INSERT INTO bots VALUES (1, '/bot', 1, 'Googlebot', '2026-11-05 00:00:00')")
    db.execute("INSERT INTO hits(site_id,path_id,browser_id,system_id,created_at) VALUES (1,1,0,0,'2026-11-05 00:00:00')")
    for table in ("store", "bots", "hits"):
        assert db.execute("SELECT count(*) FROM " + table).fetchone()[0] == 0
    db.execute("INSERT INTO paths VALUES (1,1,'/expired','',0), (2,1,'/current','',0)")
    db.execute("INSERT INTO refs VALUES (2,'expired.example','h'), (3,'current.example','h')")
    db.execute("INSERT INTO hit_counts VALUES (1,1,'2026-01-01 00:00:00',1), (1,2,'2026-11-05 00:00:00',1)")
    db.execute("INSERT INTO ref_counts VALUES (1,1,2,'2026-01-01 00:00:00',1), (1,2,3,'2026-11-05 00:00:00',1)")
    db.execute("INSERT INTO hit_stats VALUES (1,1,'2026-01-01','[1]'), (1,2,'2026-11-05','[1]')")
    db.commit()
    backups = state / "backups"
    backups.mkdir()
    (backups / "2026-10-29.sqlite3").touch()
    (backups / "2026-10-30.sqlite3").touch()
    load("maintenance").maintain(state, datetime(2026, 11, 5, 12, tzinfo=timezone.utc))
    # Owner decision 2026-11-05: statistics are kept indefinitely, so the
    # expired rows must survive maintenance; only old backups are pruned.
    for table in ("hit_counts", "ref_counts", "hit_stats", "paths"):
        assert db.execute("SELECT count(*) FROM " + table).fetchone()[0] == 2
    assert db.execute("SELECT ref FROM refs WHERE ref_id!=1 order by ref_id").fetchall() == [('expired.example',), ('current.example',)]
    assert not (backups / "2026-10-29.sqlite3").exists()
    assert (backups / "2026-10-30.sqlite3").exists()
    with sqlite3.connect(backups / "2026-11-05.sqlite3") as backup:
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert backup.execute("SELECT count(*) FROM hit_counts").fetchone()[0] == 2
    db.close()

proxy = load("collection-proxy")
captured = []


class Upstream:
    status = 200

    def __init__(self, *_args, **_kwargs):
        pass

    def request(self, method, path, headers):
        captured.append((method, parse_qs(urlsplit(path).query), headers))

    def getresponse(self):
        return self

    def read(self, *_):
        return b"gif"

    def close(self):
        pass


proxy.HTTPConnection = Upstream


def request(path, headers=None):
    handler = object.__new__(proxy.Counter)
    handler.path, handler.command, handler.headers = path, "POST", headers or {}
    replies = []
    handler.reply = lambda *response: replies.append(response)
    handler.count()
    return replies[0][0]


assert request('/count?p=%2Ftest%3Fprivate%3Dyes&r=https%3A%2F%2Fuser%3Apassword%40example.org%2Fprivate%3Fsecret%3Dyes&ip=private&ua=private', {'Cookie': 'private', 'X-Forwarded-For': 'private', 'User-Agent': 'browser'}) == 200
assert captured[-1] == ('POST', {'p': ['/test'], 'r': ['https://example.org']}, {'Host': 'stats.localhost:8081', 'User-Agent': 'browser'})
for path in ('/', '/api', '/api/v0/me', '/count.js', '/count/', '/count?p=/poster-review/'):
    assert request(path) == 404
count = len(captured)
for headers in ({'DNT': '1'}, {'Sec-GPC': '1'}):
    assert request('/count?p=/test', headers) == 200
assert len(captured) == count
print('goatcounter: guards, indefinite retention, backup expiry/integrity and proxy privacy checks passed')
