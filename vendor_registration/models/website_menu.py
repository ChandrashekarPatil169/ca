# -*- coding: utf-8 -*-

from odoo import models


class WebsiteMenu(models.Model):
    _inherit = 'website.menu'

    def _is_vendor_registration_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'vendor_registration.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')

    def _compute_visible(self):
        super()._compute_visible()
        if self._is_vendor_registration_enabled():
            return

        for menu in self:
            if menu.url in ('/vendor-registration', '/my/vendor-products'):
                menu.is_visible = False
