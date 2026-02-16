# PostgreSQL Setup & Restore

## Create DB and Role
```sql
psql -U postgres
CREATE DATABASE d2c_pricing;
CREATE USER admin WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE d2c_pricing TO admin;
\q

psql -U postgres -d d2c_pricing
GRANT ALL ON SCHEMA public TO admin;
ALTER SCHEMA public OWNER TO admin;
ALTER ROLE admin SET search_path TO public;
\q
```
Set `DATABASE_URL=postgres://admin:your_password@localhost:5432/d2c_pricing` in `.env`.

## Restore (custom pg_dump)
The backup script (`scripts/backup-d2c_pricing.js`) produces a custom `pg_dump` format (`.dump`). Restore into the target DB:
```bash
pg_restore --clean --if-exists --jobs=4 --dbname="$DATABASE_URL" d2c_pricing-YYYY-MM-DD.dump
```

If restoring into a new database name:
```bash
createdb d2c_pricing_restore
pg_restore --clean --if-exists --jobs=4 --dbname="postgres://admin:your_password@localhost:5432/d2c_pricing_restore" d2c_pricing-YYYY-MM-DD.dump
```