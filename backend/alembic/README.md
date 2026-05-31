Run migrations from `backend/`:

```
alembic upgrade head
```

Requires `DATABASE_URL` (e.g. PostgreSQL). SQLite dev installs may rely on `create_all()` instead.
