# Migration: convert is_approved/is_ordered/is_dispatched to state field
def migrate(cr, version):
    cr.execute("""
        ALTER TABLE it_asset_requisition
        ADD COLUMN IF NOT EXISTS state VARCHAR DEFAULT 'draft';
    """)
    cr.execute("""
        UPDATE it_asset_requisition
        SET state = CASE
            WHEN is_dispatched = TRUE THEN 'dispatched'
            WHEN is_ordered = TRUE THEN 'ordered'
            WHEN is_approved = TRUE THEN 'approved'
            WHEN approval_request_id IS NOT NULL THEN 'submitted'
            ELSE 'draft'
        END;
    """)
