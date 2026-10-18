# Fitness Studio Booking API

A Python + FastAPI API for a fitness studio offering Yoga, Zumba and HIIT classes. Includes SQLite persistence, token authentication, concurrency-safe booking, IST storage, timezone conversion, automatic Swagger documentation and tests.

## Requirements

- Python 3.11 or newer (tested with Python 3.12)
- pip

## Setup and run

From this project folder:

```bash
python -m venv .venv
```

Activate on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Or on macOS/Linux:

```bash
source .venv/bin/activate
```

Install and start:

```bash
python -m pip install -r requirements.txt
python seed.py
python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for Swagger UI or http://127.0.0.1:8000/redoc for reference documentation. The SQLite database is created automatically. Optional `DATABASE_PATH` overrides its location (default: `fitness.db` in the working directory). The seed script adds three future classes and skips an existing class dataset, so its examples do not become stale before the first run.

## API reference

| Method | Endpoint | Authentication | Behavior |
| --- | --- | --- | --- |
| POST | `/signup` | Public | Register name, email and password |
| POST | `/login` | Public | Return access and refresh tokens |
| POST | `/refresh` | Refresh token in body | Rotate refresh token and issue new access token |
| POST | `/classes` | Bearer token | Create a future class |
| GET | `/classes` | Public | List upcoming classes by date |
| POST | `/book` | Bearer token | Reserve one slot |
| GET | `/bookings` | Bearer token | List only the current user's bookings |

Use **Authorize** in Swagger after logging in and paste the access token. The optional `timezone` query parameter on both GET endpoints accepts IANA names such as `Asia/Kolkata`, `UTC`, or `America/New_York`.

## Example requests

The examples below use Bash/cURL. On Windows, use Swagger UI, or run them in Git Bash. Replace `ACCESS_TOKEN` with the access token returned by login. Replace the example class date if it is no longer in the future.

```bash
curl -X POST http://127.0.0.1:8000/signup \
  -H 'Content-Type: application/json' \
  -d '{"name":"Alice","email":"alice@example.com","password":"StrongPass123!"}'

curl -X POST http://127.0.0.1:8000/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"alice@example.com","password":"StrongPass123!"}'

curl -X POST http://127.0.0.1:8000/classes \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"name":"Yoga Flow","dateTime":"2027-06-15T10:00:00+05:30","instructor":"John Doe","availableSlots":20}'

curl 'http://127.0.0.1:8000/classes?timezone=UTC'

curl -X POST http://127.0.0.1:8000/book \
  -H 'Authorization: Bearer ACCESS_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"class_id":1,"client_name":"Alice","client_email":"alice@example.com"}'

curl 'http://127.0.0.1:8000/bookings?timezone=Asia/Kolkata' \
  -H 'Authorization: Bearer ACCESS_TOKEN'

curl -X POST http://127.0.0.1:8000/refresh \
  -H 'Content-Type: application/json' \
  -d '{"refresh_token":"REFRESH_TOKEN"}'
```

A class response looks like:

```json
{
  "id": 1,
  "name": "Yoga Flow",
  "dateTime": "2027-06-15T10:00:00+05:30",
  "instructor": "John Doe",
  "availableSlots": 20
}
```

A booking response contains its ID, the submitted client details, class ID and remaining `availableSlots`. `GET /bookings` returns booking details with a nested `class` object.

## Validation and design decisions

- Class timestamps must have an explicit offset and be in the future. They are normalized to `Asia/Kolkata` before storage. Query-time conversion uses Python's IANA timezone database, including daylight-saving offsets.
- Upcoming classes are publicly readable, matching the endpoint-specific requirements. Class creation, booking and booking history require authentication. Any authenticated user may create a class, as specified by the assignment.
- Booking ownership always comes from the authenticated account, never the submitted client email. The client fields are attendee contact details; they do not grant access to bookings.
- One booking per account per class. A SQLite `BEGIN IMMEDIATE` transaction serializes competing writes; the conditional decrement, insertion and commit are atomic. Failed requests roll back. A database check prevents negative capacity and a unique constraint prevents duplicate account bookings.
- Passwords are salted and hashed using scrypt. Random opaque tokens are stored only as SHA-256 digests. Access tokens expire after one hour; refresh tokens after seven days. Refresh tokens are single-use and rotated atomically; existing access tokens remain valid until expiry.
- Names and email addresses are validated; missing fields, unknown fields, invalid dates and invalid capacity return 422. Missing/invalid/expired credentials return 401, missing classes return 404, and duplicate bookings, full classes and duplicate accounts return 409.
- Request logs contain method, path and status, never passwords or tokens. Enable application logging through your server logging configuration.

## Tests

```bash
python -m pytest tests -q
```

Tests use isolated temporary SQLite databases. Coverage includes authentication, token expiration and refresh rotation, missing/invalid inputs, timezone conversion and IST persistence, filtering past classes, booking ownership, duplicates, sold-out classes and six concurrent requests for one remaining slot.

## Project structure

```text
app/
  main.py          # Application factory and HTTP endpoints
  database.py      # Schema and connection/transaction lifecycle
  schemas.py       # Request validation
  security.py      # Password hashing and token management
seed.py            # Future sample classes
sample-inputs.json # Copyable request bodies
requirements.txt
tests/test_api.py # Automated integration tests
```

## Scope

This is a local assignment implementation. Before production, add login throttling, HTTPS deployment, token cleanup/revocation, migrations, pagination and operational monitoring. SQLite is suitable for the assignment's small single-instance workload; a larger deployment should use PostgreSQL. No external services or secret API keys are required.

## Submission

Publish the contents of this folder as a **public GitHub repository**, with this README at its root. Do not upload `.venv`, `.deps`, databases, test caches or credentials. Check this README's preview in [readme.so](https://readme.so/) as requested by the assignment, then submit the public repository URL at [StarLabs assignment submission](https://www.starlabs.co.in/assignment).

The assignment specifies a deadline within three days of receipt; calculate the exact deadline from the message in which you received it.
