# -*- coding: utf-8 -*-

from odoo import models


class WebsiteMenu(models.Model):
    _inherit = 'website.menu'

    def _is_product_requisition_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'product_requisition.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')

    def _compute_visible(self):
        super()._compute_visible()
        if self._is_product_requisition_enabled():
            return

        for menu in self:
            if menu.url in ('/product-requisition', '/my/product-requisition'):
                menu.is_visible = False
