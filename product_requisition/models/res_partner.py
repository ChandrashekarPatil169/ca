# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    allow_product_requisition_bulk_upload = fields.Boolean(
        string='Allow Product Requisition Bulk Upload',
        compute='_compute_allow_product_requisition_bulk_upload',
        inverse='_inverse_allow_product_requisition_bulk_upload',
        help='When enabled, the customer can upload product requisition lines from the portal.',
    )

    def _compute_allow_product_requisition_bulk_upload(self):
        has_vendor_flag = 'allow_bulk_upload' in self._fields
        for partner in self:
            partner.allow_product_requisition_bulk_upload = (
                bool(partner.allow_bulk_upload) if has_vendor_flag else True
            )

    def _inverse_allow_product_requisition_bulk_upload(self):
        if 'allow_bulk_upload' not in self._fields:
            return
        for partner in self:
            partner.allow_bulk_upload = partner.allow_product_requisition_bulk_upload
