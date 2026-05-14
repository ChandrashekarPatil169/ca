# -*- coding: utf-8 -*-
from odoo import _, fields, models, api
from odoo.exceptions import UserError, ValidationError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    order_line_ids = fields.One2many(
        'crm.lead.products', 'lead_id', string='Order Lines'
    )
    # In Odoo 17+ company_currency was renamed to currency_id on crm.lead;
    # use the standard currency_id that already exists on the model instead
    # of creating a duplicate related field.  If a dedicated display field is
    # still needed, relate through company_id to be explicit.
    crm_currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=False,
    )
    total = fields.Monetary(
        string='Total',
        compute='_compute_total',
        currency_field='crm_currency_id',
    )

    def _is_product_requisition_module_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'product_requisition.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')

    def action_new_quotation(self):
        action = super().action_new_quotation()
        if not self._is_product_requisition_module_enabled():
            return action

        if not self.order_line_ids:
            return action

        vals = [fields.Command.clear()]
        for line in self.order_line_ids:
            line.ensure_one()
            product = line.product_id
            if product.state not in ('approved', 'mapped'):
                raise UserError(_(
                    "Product %s must be approved or mapped before creating a quotation.",
                    product.display_name,
                ))
            sale_product = product.mapped_product_id if product.state == 'mapped' and product.mapped_product_id else product
            vals.append(fields.Command.create({
                'product_id': sale_product.id,
                'name': line.name,
                'product_uom_qty': line.product_uom_qty,
                'price_unit': line.price_unit,
            }))

        if action and 'context' in action:
            action['context'].update({'default_order_line': vals})
        return action

    @api.depends('order_line_ids.price_subtotal')
    def _compute_total(self):
        for lead in self:
            lead.total = sum(lead.order_line_ids.mapped('price_subtotal'))


class CrmLeadProducts(models.Model):
    _name = 'crm.lead.products'
    _description = 'CRM Lead Order Line'

    lead_id = fields.Many2one('crm.lead', string='Lead', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    name = fields.Text(string='Description')
    product_uom_qty = fields.Float(string='Quantity', default=1.0)
    price_unit = fields.Float(string='Unit Price')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        readonly=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Currency',
        store=False,
    )
    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_subtotal',
        currency_field='currency_id',
        store=True,
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Populate description and price when a product is selected."""
        if self.product_id:
            self.price_unit = self.product_id.lst_price  # public sale price
            self.name = self.product_id.get_product_multiline_description_sale() \
                if hasattr(self.product_id, 'get_product_multiline_description_sale') \
                else self.product_id.display_name

    @api.constrains('product_id')
    def _check_product(self):
        for rec in self:
            if not rec.product_id:
                raise ValidationError("You must select a product for every order line.")

    @api.depends('product_id', 'product_uom_qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.product_uom_qty * line.price_unit
