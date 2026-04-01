#!/usr/bin/env python3
"""
Migration: Add predict_periods column to pipelines table.
Works with both SQLite and PostgreSQL.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from backend.db import SessionLocal, engine


def migrate():
    """Add predict_periods column to pipelines table."""
    db = SessionLocal()

    try:
        # Check if column already exists
        if engine.dialect.name == 'postgresql':
            result = db.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'pipelines' AND column_name = 'predict_periods'
            """))
        else:  # SQLite
            result = db.execute(text("""
                SELECT name FROM pragma_table_info('pipelines')
                WHERE name = 'predict_periods'
            """))

        if result.fetchone():
            print("Column 'predict_periods' already exists, skipping migration.")
            return

        # Add the column with default value
        if engine.dialect.name == 'postgresql':
            db.execute(text("""
                ALTER TABLE pipelines
                ADD COLUMN predict_periods INTEGER DEFAULT 1440
            """))
        else:  # SQLite
            db.execute(text("""
                ALTER TABLE pipelines
                ADD COLUMN predict_periods INTEGER DEFAULT 1440
            """))

        db.commit()
        print("Successfully added 'predict_periods' column to pipelines table.")

    except Exception as e:
        db.rollback()
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    migrate()