# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    vendor_registration_module_enabled = fields.Boolean(
        string='Enable Vendor Registration Portal',
        default=True,
        config_parameter='vendor_registration.module_enabled',
        help='Enable the website and portal vendor registration flow.',
    )

    def _get_vendor_registration_enabled_param(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'vendor_registration.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')

    def get_values(self):
        values = super().get_values()
        values.update(
            vendor_registration_module_enabled=self._get_vendor_registration_enabled_param()
        )
        return values

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'vendor_registration.module_enabled',
            'True' if self.vendor_registration_module_enabled else 'False',
        )
        self.env.registry.clear_cache()
