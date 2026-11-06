-- v2.7.0 otherwise stores bots unconditionally and empty session maps on exit.
CREATE TRIGGER privacy_no_bots BEFORE INSERT ON bots
BEGIN SELECT RAISE(IGNORE); END;
CREATE TRIGGER privacy_no_sessions BEFORE INSERT ON store
WHEN NEW.key = 'session'
BEGIN SELECT RAISE(IGNORE); END;
CREATE TRIGGER privacy_no_hits BEFORE INSERT ON hits
BEGIN SELECT RAISE(IGNORE); END;

UPDATE sites SET
  link_domain = 'https://jaromirsvoboda.github.io',
  settings = json_set(settings, '$.collect', 2, '$.data_retention', 180,
    '$.public', 'private', '$.secret', '', '$.allow_counter', json('false'),
    '$.allow_bosmang', json('false'), '$.ignore_ips', '', '$.collect_regions', '');
