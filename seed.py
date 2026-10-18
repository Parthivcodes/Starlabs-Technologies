"""Add upcoming sample classes without creating accounts or hard-coded passwords."""
import os
from datetime import datetime, timedelta
from app.database import connect, initialize
from app.main import IST

def main():
    path = os.getenv('DATABASE_PATH', 'fitness.db')
    initialize(path)
    with connect(path) as db:
        if db.execute('SELECT COUNT(*) FROM classes').fetchone()[0]:
            print('Classes already exist; seed skipped.')
            return
        for day, name in enumerate(['Yoga Flow', 'Zumba', 'HIIT Session'], start=1):
            start = (datetime.now(IST)+timedelta(days=day)).replace(hour=10, minute=0, second=0, microsecond=0)
            db.execute('INSERT INTO classes(name,date_time,instructor,available_slots) VALUES (?,?,?,?)',
                       (name, start.isoformat(), ['Jane Smith','John Doe','Priya Sharma'][day-1], 10))
    print('Created 3 upcoming classes in IST.')

if __name__ == '__main__':
    main()
