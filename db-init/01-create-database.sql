SELECT 'CREATE DATABASE veteransdb'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'veteransdb')