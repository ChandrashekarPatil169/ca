
from odoo import models, fields, api

class ITAssetRequisition(models.Model):
    _name = 'it.asset.requisition'
    _description = 'IT Asset Requisition'
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    active = fields.Boolean(default=True)

    # Status field (replaces 3 boolean toggles in list view)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('ordered', 'Ordered'),
        ('dispatched', 'Dispatched'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    color = fields.Integer(string='Color', compute='_compute_color')

    # Employee Details
    emp_first_name = fields.Char(string='First Name')
    emp_last_name = fields.Char(string='Last Name')
    emp_designation = fields.Char(string='Designation')
    emp_department = fields.Char(string='Department')
    emp_office_site = fields.Char(string='Office / Site')
    emp_code = fields.Char(string='EMP Code')
    emp_location = fields.Char(string='Location')
    request_date = fields.Date(string='Date', default=fields.Date.context_today)

    # Manager Details
    manager_first_name = fields.Char(string='Manager First Name')
    manager_last_name = fields.Char(string='Manager Last Name')
    manager_location = fields.Char(string='Manager Location')
    manager_date = fields.Date(string='Manager Date')
    manager_remarks = fields.Text(string='Manager Signature / Remarks')
    email_approval = fields.Boolean(string='Email Approval')

    # Selected Products
    hardware_product_id = fields.Many2one('product.product', string='Computer Hardware', domain="[('product_tmpl_id.asset_category','=','hardware')]")
    sim_product_id = fields.Many2one('product.product', string='Sim Card', domain="[('product_tmpl_id.asset_category','=','sim')]")
    printer_product_id = fields.Many2one('product.product', string='Printer', domain="[('product_tmpl_id.asset_category','=','printer')]")

    # Others Section
    software_checkbox = fields.Boolean(string='Software (Specify)')
    software_specify = fields.Char(string='Software Name')
    pda_checkbox = fields.Boolean(string='PDA (only for sites with CAFM)')
    pda_count = fields.Integer(string='PDA Count')
    others_text = fields.Text(string='Others')

    # Justification
    justification_type = fields.Selection([
        ('new_position', 'New Position'),
        ('new_site', 'New Site'),
        ('replacement', 'Replacement')
    ], string='Justification Type')
    justification_text = fields.Text(string='Justification')

    # IS&T Section
    reqn_rcpt_date = fields.Date(string='Reqn. Rcpt. Date')
    is_approved = fields.Boolean(string='Approved', compute='_compute_status_booleans', store=True)
    is_ordered = fields.Boolean(string='Ordered', compute='_compute_status_booleans', store=True)
    is_dispatched = fields.Boolean(string='Dispatched', compute='_compute_status_booleans', store=True)
    po_num_text = fields.Char(string='PO Num')
    old_device_sn = fields.Char(string='Old Device S/N')
    device_ageing = fields.Char(string='Device Ageing')
    make = fields.Char(string='Make')
    model_name = fields.Char(string='Model')
    ist_others = fields.Char(string='Others (IS&T)')
    ist_remark = fields.Text(string='IS&T Eng Remark')

    purchase_id = fields.Many2one('purchase.order', string='Purchase Order', readonly=True)

    @api.depends('state')
    def _compute_color(self):
        color_map = {
            'draft': 0,
            'submitted': 1,
            'approved': 3,
            'ordered': 10,
            'dispatched': 10,
            'cancelled': 9,
        }
        for rec in self:
            rec.color = color_map.get(rec.state, 0)

    @api.depends('state')
    def _compute_status_booleans(self):
        for rec in self:
            rec.is_approved = rec.state in ('approved', 'ordered', 'dispatched')
            rec.is_ordered = rec.state in ('ordered', 'dispatched')
            rec.is_dispatched = rec.state == 'dispatched'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('it.asset.requisition') or 'New'
        return super(ITAssetRequisition, self).create(vals_list)

    def create_rfq(self):
        for rec in self:
            if rec.purchase_id:
                continue

            lines = []
            selected_products = [rec.hardware_product_id, rec.sim_product_id, rec.printer_product_id]

            for product in selected_products:
                if product:
                    lines.append((0, 0, {
                        'product_id': product.id,
                        'name': product.name,
                        'product_qty': 1,
                        'price_unit': product.standard_price or 0.0,
                        'product_uom_id': product.uom_id.id,
                        'date_planned': fields.Datetime.now(),
                    }))

            if not lines:
                continue

            Partner = self.env['res.partner'].sudo()
            partner = Partner.search([('supplier_rank', '>', 0)], limit=1)
            if not partner:
                partner = Partner.search([('is_company', '=', True)], limit=1)
            if not partner:
                partner = self.env.user.partner_id

            if not partner:
                continue

            po = self.env['purchase.order'].sudo().create({
                'partner_id': partner.id,
                'origin': rec.name,
                'order_line': lines,
                'it_asset_requisition_id': rec.id,
            })
            rec.sudo().write({'purchase_id': po.id})
