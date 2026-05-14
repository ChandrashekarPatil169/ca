# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    allow_bulk_upload = fields.Boolean(
        string='Allow Bulk Product Upload (Portal)',
        default=True,
        help=(
            'When enabled, the vendor can use the Bulk Upload Products/Services '
            'section on the portal. Uncheck to hide that section for this vendor.'
        ),
    )
