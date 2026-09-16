"""
Database setup. SQLite for local prototyping. The URL is configurable
via env var, so switching to Postgres is a config change, not a code
change:

    export AEGISNET_DATABASE_URL="postgresql://user:password@localhost:5432/aegisnet"
    pip install psycopg2-binary

This file's logic is identical either way -- SQLAlchemy abstracts the
difference. NOT verified against a real Postgres server in the
environment this was written in (no network to install psycopg2 or
run a Postgres instance) -- the SQLite path IS the one actually
exercised throughout this project's development.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get("AEGISNET_DATABASE_URL", "sqlite:///./aegisnet.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
