DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dima') THEN
        CREATE USER dima WITH PASSWORD 'root';
        RAISE NOTICE 'User dima created';
    ELSE
        RAISE NOTICE 'User dima already exists';
    END IF;
END $$;

GRANT ALL PRIVILEGES ON DATABASE veteransdb TO dima;