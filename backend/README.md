# OA Backend

FastAPI backend for the first OA implementation.

Run locally:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Default app admin:

- Email: `admin@example.com`
- Password: `admin123`

Imported employees get an initial login password from `DEFAULT_EMPLOYEE_PASSWORD`.
