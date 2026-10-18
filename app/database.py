"""SQLite connections and schema. Each request owns its connection."""
import sqlite3
from contextlib import contextmanager


@contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path):
    with connect(path) as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tokens (
            digest TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, date_time TEXT NOT NULL,
            instructor TEXT NOT NULL, available_slots INTEGER NOT NULL CHECK(available_slots>=0));
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            class_id INTEGER NOT NULL REFERENCES classes(id),
            client_name TEXT NOT NULL, client_email TEXT NOT NULL,
            UNIQUE(user_id, class_id));
        CREATE INDEX IF NOT EXISTS classes_time ON classes(date_time);
        ''')
