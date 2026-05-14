# -*- coding: utf-8 -*-
from odoo import models, fields


class DealerBranch(models.Model):
    _name = 'dealer.branch'
    _description = 'Dealer Branch'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint(
        'unique(name)',
        'Branch name must be unique.',
    )


class DealerZone(models.Model):
    _name = 'dealer.zone'
    _description = 'Dealer Zone'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    _name_unique = models.Constraint(
        'unique(name)',
        'Zone name must be unique.',
    )


class DealerWarrantyType(models.Model):
    _name = 'dealer.warranty.type'
    _description = 'Warranty Type'
    _order = 'name'

    name = fields.Char(required=True)
    code = fields.Char(string="Code")
    description = fields.Char(string="Description")
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        'unique(code)',
        'Warranty type code must be unique.',
    )


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_dealer = fields.Boolean(string="Is Dealer")
    dealer_code = fields.Char(string="Dealer Code")
    branch_id = fields.Many2one('dealer.branch', string="Branch")
    zone_id = fields.Many2one('dealer.zone', string="Zone")


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    dealer_id = fields.Many2one(
        'res.partner',
        string="Dealer",
        domain=[('is_dealer', '=', True)]
    )
    dealer_code = fields.Char(
        string="Dealer Code",
        related="dealer_id.dealer_code",
        store=True,
        readonly=True
    )

class StockLot(models.Model):
    _inherit = 'stock.lot'

    active = fields.Boolean(default=True)

# Here I updated the domain that's it
    dealer_id = fields.Many2one(
        'res.partner',
        string="Dealer",
        domain=[('is_dealer', '=', True)]
    )
    dealer_code = fields.Char(
        string="Dealer Code",
        related="dealer_id.dealer_code",
        store=True,
        readonly=True
    )
    customer_id = fields.Many2one(
        'res.partner',
        string="Customer"
    )

    customer_city = fields.Char(
        related="customer_id.city",
        store=True
    )
    customer_state_id = fields.Many2one(
        related="customer_id.state_id",
        store=True
    )
    customer_zip = fields.Char(
        related="customer_id.zip",
        store=True
    )
    customer_branch_id = fields.Many2one(
        related="customer_id.branch_id",
        string="Branch",
        store=True
    )
    customer_zone_id = fields.Many2one(
        related="customer_id.zone_id",
        string="Zone",
        store=True
    )
    warranty_type_id = fields.Many2one(
        'dealer.warranty.type',
        string="Warranty Type"
    )
    warranty_description = fields.Char(
        string="Warranty Description"
    )
    product_code = fields.Char(
        related="product_id.default_code",
        string="Product Code",
        store=True
    )
    product_description = fields.Char(
        related="product_id.name",
        string="Product Description"
    )
    product_category_id = fields.Many2one(
        related="product_id.categ_id",
        string="Product Category",
        store=True
    )
    product_category_code = fields.Char(
        related="product_category_id.dealer_category_code",
        string="Product Category Code",
        store=True
    )
    product_category_description = fields.Char(
        related="product_category_id.dealer_category_description",
        string="Product Category Description",
        store=True
    )


class ProductCategory(models.Model):
    _inherit = 'product.category'

    dealer_category_code = fields.Char(string="Category Code")
    dealer_category_description = fields.Char(string="Category Description")


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    dealer_category_code = fields.Char(
        related="categ_id.dealer_category_code",
        string="Category Code",
        readonly=True
    )
    dealer_category_description = fields.Char(
        related="categ_id.dealer_category_description",
        string="Category Description",
        readonly=True
    )


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _action_done(self):
        res = super()._action_done()

        for line in self:
            if line.lot_id and line.move_id.sale_line_id:
                sale_order = line.move_id.sale_line_id.order_id

                # Set Customer
                line.lot_id.customer_id = sale_order.partner_id.id

                # Set Dealer
                line.lot_id.dealer_id = sale_order.dealer_id.id
                line.lot_id.dealer_code = sale_order.dealer_code

        return res
