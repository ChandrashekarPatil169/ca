# -*- coding: utf-8 -*-
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import _, fields, models, api
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        for order in self:
            missing_vendor_lines = order.order_line.filtered(
                lambda line: not line.display_type and line.is_dropship and not line.vendor_ids
            )
            if missing_vendor_lines:
                raise UserError(_("Please select vendors for dropship lines."))
            order._apply_requisition_routes()
        result = super().action_confirm()
        self._create_vendor_rfqs()
        return result

    def _apply_requisition_routes(self):
        dropship_route = self.env.ref('stock_dropshipping.route_drop_shipping', raise_if_not_found=False)
        if not dropship_route:
            return
        for line in self.order_line.filtered(lambda sol: not sol.display_type and sol.product_id):
            routes = line.route_ids
            if line.is_dropship and line.vendor_ids:
                if dropship_route not in routes:
                    line.route_ids = [fields.Command.link(dropship_route.id)]
            else:
                if dropship_route in routes:
                    line.route_ids = [fields.Command.unlink(dropship_route.id)]

    def _get_dropship_picking_type(self):
        self.ensure_one()
        return self.env['stock.picking.type'].search([
            ('code', '=', 'dropship'),
            '|',
            ('company_id', '=', self.company_id.id),
            ('company_id', '=', False),
        ], limit=1, order='sequence')

    def _create_vendor_rfqs(self):
        PurchaseOrder = self.env['purchase.order'].sudo()
        PurchaseOrderLine = self.env['purchase.order.line'].sudo()
        for order in self:
            grouped_lines = defaultdict(lambda: self.env['sale.order.line'])
            vendor_has_dropship = defaultdict(bool)
            dropship_type = order._get_dropship_picking_type()
            incoming_type = order.warehouse_id.in_type_id

            for line in order.order_line.filtered(lambda sol: not sol.display_type and sol.vendor_ids):
                product = line.product_id
                if product.state not in ('approved', 'mapped'):
                    raise UserError(_("Product %s must be approved or mapped.", product.display_name))
                for vendor in line.vendor_ids:
                    if PurchaseOrderLine.search_count([
                        ('sale_line_id', '=', line.id),
                        ('order_id.partner_id', '=', vendor.id),
                    ]):
                        continue
                    grouped_lines[vendor.id] |= line
                    vendor_has_dropship[vendor.id] = vendor_has_dropship[vendor.id] or (
                                line.is_dropship and bool(line.vendor_ids))
            for vendor_id, lines in grouped_lines.items():
                vendor = self.env['res.partner'].sudo().browse(vendor_id)
                picking_type = dropship_type if vendor_has_dropship[vendor_id] else incoming_type
                if vendor_has_dropship[vendor_id] and not picking_type:
                    raise UserError(_("No dropship operation type is configured for %s.", order.company_id.display_name))
                fpos = self.env['account.fiscal.position'].sudo()._get_fiscal_position(vendor)
                purchase_order = PurchaseOrder.create({
                    'partner_id': vendor.id,
                    'partner_ref': vendor.ref,
                    'company_id': order.company_id.id,
                    'currency_id': vendor.property_purchase_currency_id.id or order.company_id.currency_id.id,
                    'origin': order.name,
                    'payment_term_id': vendor.property_supplier_payment_term_id.id,
                    'date_order': fields.Datetime.now(),
                    'fiscal_position_id': fpos.id,
                    'picking_type_id': picking_type.id if picking_type else False,
                    'dest_address_id': order.partner_shipping_id.id if picking_type and picking_type.code == 'dropship' else False,
                })
                for line in lines:
                    PurchaseOrderLine.create(line._prepare_selected_vendor_purchase_line(purchase_order))

    @api.onchange('sale_order_template_id')
    def _onchange_sale_order_template_id(self):
        """Override to skip template-based line reset when the order came from
        a CRM opportunity that already has custom order lines loaded via
        action_new_quotation (context key ``default_order_line``).

        In Odoo 19 the sale.order.template onchange is handled by the core
        ``_onchange_sale_order_template_id`` method.  We only need to guard
        the case where an opportunity is linked so that CRM-sourced lines are
        not wiped out when a template is later applied manually.
        """
        # Let the standard logic run first
        res = super()._onchange_sale_order_template_id()

        # If this SO is linked to an opportunity and the template change would
        # clear lines, restore the lines coming from the CRM context so they
        # are not lost unexpectedly.  Users can still clear them manually.
        if self.opportunity_id and self.sale_order_template_id:
            # Retrieve CRM-sourced lines from context if present
            crm_lines = self.env.context.get('default_order_line')
            if crm_lines:
                self.order_line = crm_lines

        return res


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    vendor_ids = fields.Many2many(
        'res.partner',
        'sale_order_line_vendor_rel',
        'sale_line_id',
        'partner_id',
        string='Vendors',
    )
    is_dropship = fields.Boolean(string='Dropship', default=True)

    def _action_launch_stock_rule(self, *, previous_product_uom_qty=False):
        return super(SaleOrderLine, self.filtered(lambda line: not line.is_dropship))._action_launch_stock_rule(
            previous_product_uom_qty=previous_product_uom_qty,
        )

    def _prepare_selected_vendor_purchase_line(self, purchase_order):
        self.ensure_one()
        vendor = purchase_order.partner_id
        product_qty = self.product_uom_id._compute_quantity(self.product_uom_qty, self.product_id.uom_id)
        seller = self.product_id._select_seller(
            partner_id=vendor,
            quantity=product_qty,
            date=fields.Date.context_today(self),
            uom_id=self.product_id.uom_id,
        )
        purchase_uom = seller.product_uom_id or self.product_id.uom_id
        purchase_qty = self.product_id.uom_id._compute_quantity(product_qty, purchase_uom)
        supplier_taxes = self.product_id.supplier_taxes_id.filtered(
            lambda tax: tax.company_id in purchase_order.company_id.parent_ids
        )
        taxes = purchase_order.fiscal_position_id.map_tax(supplier_taxes) if purchase_order.fiscal_position_id else supplier_taxes
        price_unit = seller.price if seller else self.product_id.standard_price
        if seller and seller.currency_id != purchase_order.currency_id:
            price_unit = seller.currency_id._convert(
                price_unit,
                purchase_order.currency_id,
                purchase_order.company_id,
                fields.Date.context_today(self),
            )
        name = self.product_id.with_context(lang=vendor.lang).display_name
        if self.product_id.description_purchase:
            name += '\n' + self.product_id.description_purchase
        delay = int(seller.delay) if seller else 0
        return {
            'order_id': purchase_order.id,
            'sale_line_id': self.id,
            'product_id': self.product_id.id,
            'name': name,
            'product_qty': purchase_qty,
            'product_uom_id': purchase_uom.id,
            'price_unit': price_unit,
            'date_planned': purchase_order.date_order + relativedelta(days=delay),
            'tax_ids': [fields.Command.set(taxes.ids)],
        }
