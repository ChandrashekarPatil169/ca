# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class VendorProductRequest(models.Model):
    _name = 'vendor.product.request'
    _description = 'Vendor Product / Service Registration Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # -------------------------------------------------------------------------
    # Basic Information
    # -------------------------------------------------------------------------

    name = fields.Char(
        string='Product / Service Name',
        required=True,
        tracking=True
    )

    vendor_registration_id = fields.Many2one(
        'vendor.registration',
        string='Vendor',
        required=True,
        ondelete='cascade'
    )

    partner_id = fields.Many2one(
        'res.partner',
        related='vendor_registration_id.partner_id',
        string='Vendor Contact',
        store=True
    )

    product_type = fields.Selection([
        ('goods', 'Goods'),
        ('service', 'Service'),
    ],
        string='Type',
        required=True,
        default='goods'
    )

    description = fields.Text(string='Description')

    internal_notes = fields.Text(string='Internal Notes')

    # -------------------------------------------------------------------------
    # Commercial Information
    # -------------------------------------------------------------------------

    uom = fields.Char(string='Unit of Measure')

    price = fields.Float(string='Offered Price / Rate')

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    min_order_qty = fields.Float(
        string='Minimum Order Quantity',
        default=1.0
    )

    lead_time = fields.Integer(string='Lead Time (days)')

    # OFFICIAL ODOO HSN FIELD
    l10n_in_hsn_code = fields.Char(
        string='HSN / SAC Code',
        tracking=True
    )

    tax_percent = fields.Float(string='Applicable GST %')

    brand = fields.Char(string='Brand / Make')

    model_number = fields.Char(string='Model / Part Number')

    certifications = fields.Char(string='Certifications / Standards')

    # -------------------------------------------------------------------------
    # Status
    # -------------------------------------------------------------------------

    state = fields.Selection([
        ('draft', 'Requested'),
        ('approved', 'Approved'),
        ('merged', 'Merged with Existing'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    # -------------------------------------------------------------------------
    # Approval Tracking
    # -------------------------------------------------------------------------

    product_id = fields.Many2one(
        'product.template',
        string='Linked Product',
        readonly=True
    )

    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True
    )

    approved_date = fields.Datetime(
        string='Approved On',
        readonly=True
    )

    existing_product_id = fields.Many2one(
        'product.template',
        string='Merge / Map to Existing Product',
        domain="[('active', '=', True)]",
        help="If this product already exists in the catalog, "
             "select it here to link the vendor as a supplier.",
    )

    product_count = fields.Integer(
        string='Product Count',
        compute='_compute_product_count'
    )

    @api.model
    def _is_vendor_registration_module_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'vendor_registration.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')

    @api.model
    def _check_vendor_registration_module_enabled(self):
        if not self._is_vendor_registration_module_enabled():
            raise UserError(_('Vendor registration is currently disabled.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_vendor_registration_module_enabled()
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # Open Product
    # -------------------------------------------------------------------------

    def action_open_product(self):

        self.ensure_one()

        if not self.product_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': 'Product',
            'res_model': 'product.template',
            'view_mode': 'form',
            'res_id': self.product_id.id,
            'target': 'current',
        }

    def _compute_product_count(self):

        for rec in self:
            rec.product_count = 1 if rec.product_id else 0

    def _get_product_type_label(self):

        self.ensure_one()

        selection = self._fields['product_type'].selection

        if callable(selection):
            selection = selection(self)

        return dict(selection).get(
            self.product_type,
            self.product_type or ''
        )

    # -------------------------------------------------------------------------
    # Approve
    # -------------------------------------------------------------------------

    def action_approve(self):
        self._check_vendor_registration_module_enabled()

        for rec in self:

            if rec.state != 'draft':
                raise UserError(
                    _('Only pending requests can be approved.')
                )

            # -------------------------------------------------------------
            # Merge Existing Product
            # -------------------------------------------------------------

            if rec.existing_product_id:

                rec._add_vendor_to_product(
                    rec.existing_product_id
                )

                rec.write({
                    'state': 'merged',
                    'product_id': rec.existing_product_id.id,
                    'approved_by': self.env.user.id,
                    'approved_date': fields.Datetime.now(),
                })

            # -------------------------------------------------------------
            # Create New Product
            # -------------------------------------------------------------

            else:

                mapping = {
                    'goods': 'consu',
                    'service': 'service',
                }

                product_type = mapping.get(
                    rec.product_type,
                    'consu'
                )

                valid_types = dict(
                    self.env['product.template']
                    ._fields['type']
                    .selection
                ).keys()

                if product_type not in valid_types:
                    product_type = list(valid_types)[0]

                product_vals = {

                    'name': rec.name,

                    'type': product_type,

                    'description': rec.description or '',

                    'description_purchase': rec.description or '',

                    'standard_price': rec.price or 0.0,

                    'uom_id': rec._get_uom(rec.uom),

                    'purchase_ok': True,

                    'sale_ok': product_type != 'service',

                    # HSN
                    'l10n_in_hsn_code': rec.l10n_in_hsn_code or False,
                }

                product = self.env[
                    'product.template'
                ].create(product_vals)

                # Add Vendor
                rec._add_vendor_to_product(product)

                rec.write({
                    'state': 'approved',
                    'product_id': product.id,
                    'approved_by': self.env.user.id,
                    'approved_date': fields.Datetime.now(),
                })

    # -------------------------------------------------------------------------
    # Reject
    # -------------------------------------------------------------------------

    def action_reject(self):

        for rec in self:
            rec.state = 'rejected'

    # -------------------------------------------------------------------------
    # Reset Draft
    # -------------------------------------------------------------------------

    def action_reset_draft(self):

        for rec in self:
            rec.state = 'draft'

    # -------------------------------------------------------------------------
    # Add Vendor to Product
    # -------------------------------------------------------------------------

    def _add_vendor_to_product(self, product_tmpl):

        self.ensure_one()

        partner = self.vendor_registration_id.partner_id

        if not partner:
            return

        existing = self.env['product.supplierinfo'].search([
            ('product_tmpl_id', '=', product_tmpl.id),
            ('partner_id', '=', partner.id),
        ], limit=1)

        if existing:
            return

        self.env['product.supplierinfo'].create({
            'product_tmpl_id': product_tmpl.id,
            'partner_id': partner.id,
            'price': self.price or 0.0,
            'min_qty': self.min_order_qty or 1.0,
            'delay': self.lead_time or 0,
        })

    # -------------------------------------------------------------------------
    # UOM Helper
    # -------------------------------------------------------------------------

    def _get_uom(self, uom_name):

        if not uom_name:
            return self.env.ref(
                'uom.product_uom_unit'
            ).id

        uom = self.env['uom.uom'].search([
            ('name', 'ilike', uom_name)
        ], limit=1)

        if uom:
            return uom.id

        return self.env.ref(
            'uom.product_uom_unit'
        ).id


# -----------------------------------------------------------------------------
# Partner Product Count
# -----------------------------------------------------------------------------

class ResPartner(models.Model):
    _inherit = 'res.partner'

    product_count = fields.Integer(
        compute="_compute_product_count"
    )

    def _compute_product_count(self):

        ProductRequest = self.env['vendor.product.request']

        for partner in self:

            related_requests = ProductRequest.search([
                '|',
                ('partner_id', '=', partner.id),
                ('partner_id.commercial_partner_id', '=', partner.id),
            ])

            partner.product_count = len(
                related_requests.filtered(
                    lambda r:
                    r.state in ['approved', 'merged']
                    and r.product_id
                )
            )

    def action_open_products(self):

        self.ensure_one()

        requests = self.env[
            'vendor.product.request'
        ].search([
            '|',
            ('partner_id', '=', self.id),
            ('partner_id.commercial_partner_id', '=', self.id),
        ])

        product_ids = requests.filtered(
            lambda r:
            r.state in ['approved', 'merged']
            and r.product_id
        ).mapped('product_id').ids

        return {
            'type': 'ir.actions.act_window',
            'name': 'Products',
            'res_model': 'product.template',
            'view_mode': 'list,form',
            'domain': [('id', 'in', product_ids)],
        }
