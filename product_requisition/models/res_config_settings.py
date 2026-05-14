# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    product_requisition_module_enabled = fields.Boolean(
        string='Enable Product Requisition',
        default=True,
        config_parameter='product_requisition.module_enabled',
        help='Enable the website, portal, and backend product requisition flow.',
    )

    def _get_product_requisition_enabled_param(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'product_requisition.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')

    def _get_product_requisition_backend_view_xmlids(self):
        return (
            'dgz_crm_orderlines.dgz_sale_order_form_requisition_purchase',
            'dgz_crm_orderlines.dgz_crm_lead_inherited',
            'product_requisition.view_partner_product_requisition_bulk_upload',
            'product_requisition.product_requisition_sale_order_form',
            'product_requisition.product_requisition_product_template_ecommerce_categories',
            'product_requisition.product_requisition_product_variant_ecommerce_categories',
            'product_requisition.product_requisition_crm_lead_form',
            'zb_product_approve.product_template_view_order_form_inherit_zb_product_approve',
            'zb_product_approve.product_product_view_order_form_inherit_zb_product_approve',
            'zb_product_approve.product_template_view_tree_inherit_zb_product_approve',
            'zb_product_approve.product_product_view_tree_inherit_zb_product_approve',
            'zb_product_approve.product_template_search_view_inherit_zb_product_approve',
        )

    def _get_product_requisition_backend_action_xmlids(self):
        return {
            'zb_product_approve.action_draft_all': 'product.model_product_template',
            'zb_product_approve.action_verify_all': 'product.model_product_template',
            'zb_product_approve.action_draft_all_product': 'product.model_product_product',
            'zb_product_approve.action_verify_all_product': 'product.model_product_product',
        }

    def _sync_product_requisition_backend_views(self, enabled):
        views = self.env['ir.ui.view'].sudo()
        for xmlid in self._get_product_requisition_backend_view_xmlids():
            view = self.env.ref(xmlid, raise_if_not_found=False)
            if view and view.active != enabled:
                views |= view
        if views:
            views.write({'active': enabled})

    def _sync_product_requisition_backend_actions(self, enabled):
        for xmlid, model_xmlid in self._get_product_requisition_backend_action_xmlids().items():
            action = self.env.ref(xmlid, raise_if_not_found=False)
            if not action:
                continue

            binding_model = (
                self.env.ref(model_xmlid, raise_if_not_found=False)
                if enabled else self.env['ir.model']
            )
            if action.binding_model_id != binding_model:
                action.write({'binding_model_id': binding_model.id})

    def _sync_product_requisition_backend_records(self, enabled):
        self._sync_product_requisition_backend_views(enabled)
        self._sync_product_requisition_backend_actions(enabled)

    def _register_hook(self):
        super()._register_hook()
        enabled = self._get_product_requisition_enabled_param()
        self._sync_product_requisition_backend_records(enabled)

    def get_values(self):
        values = super().get_values()
        enabled = self._get_product_requisition_enabled_param()
        self._sync_product_requisition_backend_records(enabled)
        values.update(
            product_requisition_module_enabled=enabled
        )
        return values

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'product_requisition.module_enabled',
            'True' if self.product_requisition_module_enabled else 'False',
        )
        self._sync_product_requisition_backend_records(
            self.product_requisition_module_enabled
        )
        self.env.registry.clear_cache()
