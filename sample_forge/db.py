"""Librería de samples en SQLite, con búsqueda de texto completo (FTS5)."""
import re
import sqlite3
import threading
import time

SCHEMA = """
create table if not exists samples(
  id text primary key, kind text, prompt text, file text, loop integer, duration real,
  peak_db real, rms_db real, f0 real, note text, tags text, credits integer, created real);
create virtual table if not exists fts using fts5(id unindexed, prompt, tags);
create table if not exists ledger(ts real, credits integer, sample_id text);
"""


class DB:
    def __init__(self, path):
        self.c = sqlite3.connect(path, check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.lock = threading.Lock()      # el worker de jobs escribe desde hilos
        self.c.executescript(SCHEMA)

    def get(self, id):
        with self.lock:
            r = self.c.execute("select * from samples where id=?", (id,)).fetchone()
        return dict(r) if r else None

    def add(self, s):
        with self.lock, self.c:
            self.c.execute("insert into samples values(:id,:kind,:prompt,:file,:loop,:duration,:peak_db,:rms_db,"
                           ":f0,:note,:tags,:credits,:created)", s)
            self.c.execute("insert into fts values(?,?,?)", (s["id"], s["prompt"], s["tags"]))
            self.c.execute("insert into ledger values(?,?,?)", (s["created"], s["credits"], s["id"]))

    def search(self, q="", kind=None, note=None, max_dur=None, limit=100):
        sql, args = "select s.* from samples s", []
        where = []
        tokens = re.findall(r"\w+", q.lower())
        if tokens:      # solo \w: no se puede colar sintaxis FTS. Cada término es prefijo y se combinan con AND
            sql += " join fts on fts.id = s.id"
            where.append("fts match ?")
            args.append(" ".join(t + "*" for t in tokens))
        if kind:
            where.append("s.kind = ?"), args.append(kind)
        if note:        # "A" = cualquier octava de La; "A4" = esa nota exacta
            where.append("(s.note = ? or substr(s.note, 1, length(s.note) - 1) = ?)"), args.extend([note, note])
        if max_dur:
            where.append("s.duration <= ?"), args.append(max_dur)
        if where:
            sql += " where " + " and ".join(where)
        with self.lock:
            return [dict(r) for r in self.c.execute(sql + " order by s.created desc limit ?", args + [limit])]

    def spent_since(self, ts):
        with self.lock:
            return self.c.execute("select coalesce(sum(credits), 0) from ledger where ts >= ?", (ts,)).fetchone()[0]


def month_start(now=None):
    t = time.localtime(now or time.time())
    return time.mktime((t.tm_year, t.tm_mon, 1, 0, 0, 0, 0, 0, -1))
