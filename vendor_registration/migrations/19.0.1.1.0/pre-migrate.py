# -*- coding: utf-8 -*-
"""
Migration 19.0.1.1.0
Add allow_bulk_upload boolean column to res_partner (default True).
Running this in pre-migrate guarantees the column exists before the ORM
tries to read or write it during the module load.
"""


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE res_partner
        ADD COLUMN IF NOT EXISTS allow_bulk_upload BOOLEAN NOT NULL DEFAULT TRUE;
    """)
