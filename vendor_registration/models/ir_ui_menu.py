# -*- coding: utf-8 -*-

from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _is_vendor_registration_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'vendor_registration.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')

    def _load_menus_blacklist(self):
        menu_ids = list(super()._load_menus_blacklist())
        if self._is_vendor_registration_enabled():
            return menu_ids

        hidden_xmlids = (
            'vendor_registration.menu_vendor_registration_purchase_root',
            'vendor_registration.menu_vendor_registration_purchase_requested',
            'vendor_registration.menu_vendor_registration_purchase_all',
            'vendor_registration.menu_vendor_product_request_purchase',
            'vendor_registration.menu_vendor_product_request_inventory',
        )
        hidden_menu_ids = [
            menu.id
            for menu in (
                self.env.ref(xmlid, raise_if_not_found=False)
                for xmlid in hidden_xmlids
            )
            if menu
        ]
        return menu_ids + hidden_menu_ids
