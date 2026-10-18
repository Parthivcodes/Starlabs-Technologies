"""Fitness studio booking API; run with uvicorn app.main:app."""
import logging
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from .database import connect, initialize
from .schemas import BookingInput, ClassInput, Login, RefreshInput, Signup
from .security import hash_password, issue_tokens, token_digest, verify_password

IST = ZoneInfo('Asia/Kolkata')
bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger('fitness.api')


def now_ist():
    return datetime.now(IST).isoformat(timespec='microseconds')


def timezone_value(timezone: str = Query('Asia/Kolkata')):
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, 'Unknown IANA timezone')


def present_class(row, zone):
    return {'id': row['id'], 'name': row['name'],
            'dateTime': datetime.fromisoformat(row['date_time']).astimezone(zone).isoformat(),
            'instructor': row['instructor'], 'availableSlots': row['available_slots']}


def create_app(database_path=None):
    path = str(database_path or os.getenv('DATABASE_PATH', 'fitness.db'))

    @asynccontextmanager
    async def lifespan(app):
        initialize(path)
        yield

    api = FastAPI(title='Fitness Studio Booking API', version='1.0.0', lifespan=lifespan)

    @api.middleware('http')
    async def log_request(request, call_next):
        response = await call_next(request)
        logger.info('%s %s %s', request.method, request.url.path, response.status_code)
        return response

    def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if credentials:
            with connect(path) as db:
                row = db.execute('SELECT user_id FROM tokens WHERE digest=? AND kind=? AND expires>?',
                                 (token_digest(credentials.credentials), 'access', time.time())).fetchone()
                if row:
                    return row['user_id']
        raise HTTPException(401, 'Invalid or expired bearer token', headers={'WWW-Authenticate': 'Bearer'})

    @api.post('/signup', status_code=201, tags=['Authentication'])
    def signup(data: Signup):
        try:
            with connect(path) as db:
                result = db.execute('INSERT INTO users(name,email,password_hash) VALUES (?,?,?)',
                                    (data.name, data.email, hash_password(data.password)))
                return {'id': result.lastrowid, 'name': data.name, 'email': data.email}
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'Email already registered')

    @api.post('/login', tags=['Authentication'])
    def login(data: Login):
        with connect(path) as db:
            user = db.execute('SELECT * FROM users WHERE email=?', (data.email,)).fetchone()
            if not user or not verify_password(data.password, user['password_hash']):
                raise HTTPException(401, 'Invalid email or password')
            return issue_tokens(db, user['id'])

    @api.post('/refresh', tags=['Authentication'])
    def refresh(data: RefreshInput):
        with connect(path) as db:
            db.execute('BEGIN IMMEDIATE')
            digest = token_digest(data.refresh_token)
            token = db.execute('SELECT * FROM tokens WHERE digest=? AND kind=? AND expires>?',
                               (digest, 'refresh', time.time())).fetchone()
            if not token:
                raise HTTPException(401, 'Invalid or expired refresh token')
            db.execute('DELETE FROM tokens WHERE digest=?', (digest,))
            return issue_tokens(db, token['user_id'])

    @api.post('/classes', status_code=201, tags=['Classes'])
    def create_class(data: ClassInput, user=Depends(current_user)):
        date_time = data.dateTime.astimezone(IST).isoformat(timespec='microseconds')
        if date_time <= now_ist():
            raise HTTPException(422, 'Class must start in the future')
        with connect(path) as db:
            result = db.execute('INSERT INTO classes(name,date_time,instructor,available_slots) VALUES (?,?,?,?)',
                                (data.name, date_time, data.instructor, data.availableSlots))
            return present_class(db.execute('SELECT * FROM classes WHERE id=?', (result.lastrowid,)).fetchone(), IST)

    @api.get('/classes', tags=['Classes'])
    def classes(zone=Depends(timezone_value)):
        with connect(path) as db:
            return [present_class(row, zone) for row in db.execute(
                'SELECT * FROM classes WHERE date_time>? ORDER BY date_time,id', (now_ist(),))]

    @api.post('/book', status_code=201, tags=['Bookings'])
    def book(data: BookingInput, user=Depends(current_user)):
        with connect(path) as db:
            # Reserve the write lock before reading; slot decrement and booking commit together.
            db.execute('BEGIN IMMEDIATE')
            fitness_class = db.execute('SELECT * FROM classes WHERE id=?', (data.class_id,)).fetchone()
            if not fitness_class:
                raise HTTPException(404, 'Class not found')
            if fitness_class['date_time'] <= now_ist():
                raise HTTPException(409, 'Class has already started')
            if db.execute('SELECT 1 FROM bookings WHERE user_id=? AND class_id=?', (user, data.class_id)).fetchone():
                raise HTTPException(409, 'You have already booked this class')
            result = db.execute('UPDATE classes SET available_slots=available_slots-1 WHERE id=? AND available_slots>0',
                                (data.class_id,))
            if result.rowcount != 1:
                raise HTTPException(409, 'No slots available')
            booking = db.execute('INSERT INTO bookings(user_id,class_id,client_name,client_email) VALUES (?,?,?,?)',
                                 (user, data.class_id, data.client_name, str(data.client_email).lower()))
            return {'id': booking.lastrowid, **data.model_dump(), 'availableSlots': fitness_class['available_slots'] - 1}

    @api.get('/bookings', tags=['Bookings'])
    def bookings(user=Depends(current_user), zone=Depends(timezone_value)):
        with connect(path) as db:
            rows = db.execute('''SELECT b.id AS booking_id,b.client_name,b.client_email,c.*
                                 FROM bookings b JOIN classes c ON c.id=b.class_id
                                 WHERE b.user_id=? ORDER BY c.date_time,b.id''', (user,))
            return [{'id': r['booking_id'], 'client_name': r['client_name'], 'client_email': r['client_email'],
                     'class': present_class(r, zone)} for r in rows]

    return api


app = create_app()
