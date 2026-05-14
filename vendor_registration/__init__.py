# -*- coding: utf-8 -*-
from . import models
from . import controllers


def post_init_hook(env):
    """
    After install:
    1. Ensure allow_bulk_upload column exists on res_partner.
    2. Explicitly link our views to the window actions.
    """
    # Safety net: create column if ORM migration hasn't run yet
    env.cr.execute("""
        ALTER TABLE res_partner
        ADD COLUMN IF NOT EXISTS allow_bulk_upload BOOLEAN NOT NULL DEFAULT TRUE;
    """)

    IrView = env['ir.ui.view']

    form_view = IrView.search([
        ('model', '=', 'vendor.registration'),
        ('type', '=', 'form'),
        ('name', '=', 'vendor.registration.form'),
    ], limit=1)

    list_view = IrView.search([
        ('model', '=', 'vendor.registration'),
        ('type', '=', 'list'),
        ('name', '=', 'vendor.registration.list'),
    ], limit=1)

    if not form_view or not list_view:
        return

    for action_xml_id in [
        'vendor_registration.action_vendor_registration_requested',
        'vendor_registration.action_vendor_registration_all',
    ]:
        try:
            action = env.ref(action_xml_id)
        except Exception:
            continue

        action.view_ids.unlink()
        env['ir.actions.act_window.view'].create({
            'sequence': 1,
            'view_mode': 'list',
            'view_id': list_view.id,
            'act_window_id': action.id,
        })
        env['ir.actions.act_window.view'].create({
            'sequence': 2,
            'view_mode': 'form',
            'view_id': form_view.id,
            'act_window_id': action.id,
        })
