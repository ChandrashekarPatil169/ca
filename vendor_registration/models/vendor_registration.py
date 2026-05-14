# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError
import secrets
import string


class VendorRegistration(models.Model):
    _name = 'vendor.registration'
    _description = 'Vendor Registration Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # ── Basic Info ──────────────────────────────────────────────────────────
    name = fields.Char(string='Company / Vendor Name', required=True, tracking=True)
    contact_name = fields.Char(string='Contact Person Name', required=True)
    email = fields.Char(string='Email', required=True, tracking=True)
    phone = fields.Char(string='Phone', required=True)
    mobile = fields.Char(string='Mobile')
    website = fields.Char(string='Website')

    # ── Business Details ────────────────────────────────────────────────────
    company_type = fields.Selection([
        ('individual', 'Individual / Proprietorship'),
        ('partnership', 'Partnership'),
        ('llp', 'LLP'),
        ('private_ltd', 'Private Limited'),
        ('public_ltd', 'Public Limited'),
        ('other', 'Other'),
    ], string='Business Type', required=True, default='individual')

    gst_number = fields.Char(string='GST Number', tracking=True)
    l10n_in_gst_treatment = fields.Selection([
        ('regular', 'Registered Business - Regular'),
        ('composition', 'Registered Business - Composition'),
        ('unregistered', 'Unregistered Business'),
        ('consumer', 'Consumer'),
        ('overseas', 'Overseas'),
        ('special_economic_zone', 'Special Economic Zone'),
        ('deemed_export', 'Deemed Export'),
        ('uin_holders', 'UIN Holders'),
    ], string='GST Treatment', default='unregistered')
    pan_number = fields.Char(string='PAN Number')
    cin_number = fields.Char(string='CIN Number')
    msme_number = fields.Char(string='MSME / Udyam Registration Number')

    # ── Address ─────────────────────────────────────────────────────────────
    street = fields.Char(string='Street / Address Line 1')
    street2 = fields.Char(string='Address Line 2')
    city = fields.Char(string='City')
    zip = fields.Char(string='PIN Code')
    state_id = fields.Many2one('res.country.state', string='State',
                               domain="[('country_id', '=', country_id)]")
    country_id = fields.Many2one('res.country', string='Country',
                                 default=lambda self: self.env.ref('base.in', raise_if_not_found=False))

    # ── Bank Details ─────────────────────────────────────────────────────────
    bank_name = fields.Char(string='Bank Name')
    bank_account_number = fields.Char(string='Bank Account Number')
    bank_ifsc = fields.Char(string='IFSC Code')
    bank_branch = fields.Char(string='Branch Name')

    # ── Additional ──────────────────────────────────────────────────────────
    years_in_business = fields.Integer(string='Years in Business')
    annual_turnover = fields.Selection([
        ('below_10l', 'Below ₹10 Lakhs'),
        ('10l_50l', '₹10 – 50 Lakhs'),
        ('50l_1cr', '₹50 Lakhs – 1 Crore'),
        ('1cr_10cr', '₹1 – 10 Crores'),
        ('above_10cr', 'Above ₹10 Crores'),
    ], string='Annual Turnover')
    notes = fields.Text(string='Additional Notes / Remarks')

    # ── State & Linking ─────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    partner_id = fields.Many2one('res.partner', string='Linked Contact', readonly=True)
    user_id = fields.Many2one('res.users', string='Portal User', readonly=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approved_date = fields.Datetime(string='Approved On', readonly=True)

    allow_bulk_upload = fields.Boolean(
        string='Allow Bulk Product Upload (Portal)',
        related='partner_id.allow_bulk_upload',
        readonly=False,
        store=False,
        help='Uncheck to hide the Bulk Upload section from this vendor\'s portal page.',
    )

    # ── Computed ────────────────────────────────────────────────────────────
    product_request_count = fields.Integer(
        string='Product Requests',
        compute='_compute_product_request_count',
    )

    @api.depends('state')
    def _compute_product_request_count(self):
        for rec in self:
            rec.product_request_count = self.env['vendor.product.request'].search_count(
                [('vendor_registration_id', '=', rec.id)]
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
        records = super().create(vals_list)
        records._check_active_gst_duplicate()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'gst_number', 'state'} & set(vals):
            self._check_active_gst_duplicate()
        return result

    # ── Constraints ─────────────────────────────────────────────────────────
    @api.constrains('gst_number')
    def _check_gst(self):
        for rec in self:
            if rec.gst_number and len(rec.gst_number) != 15:
                raise UserError(_('GST Number must be exactly 15 characters.'))

    @api.constrains('gst_number', 'state')
    def _check_active_gst_duplicate(self):
        for rec in self.filtered(lambda r: r.gst_number and r.state in ('draft', 'approved')):
            duplicate = self.search([
                ('id', '!=', rec.id),
                ('gst_number', '=', rec.gst_number),
                ('state', 'in', ('draft', 'approved')),
            ], limit=1)
            if duplicate:
                raise UserError(_(
                    'A registration with this GST number is already pending or approved.'
                ))

    def _get_product_registration_url(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return '%s/web/login?redirect=' % base_url

    # ── Actions ─────────────────────────────────────────────────────────────
    def action_approve(self):
        self._check_vendor_registration_module_enabled()
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only pending requests can be approved.'))

            # 1. Create / find partner
            partner = self.env['res.partner'].search([('email', '=', rec.email)], limit=1)
            if not partner:
                partner_vals = {
                    'name': rec.name,
                    'company_type': 'company' if rec.company_type != 'individual' else 'person',
                    'email': rec.email,
                    'phone': rec.phone,
                    'website': rec.website,
                    'street': rec.street,
                    'street2': rec.street2,
                    'city': rec.city,
                    'zip': rec.zip,
                    'state_id': rec.state_id.id,
                    'country_id': rec.country_id.id,
                    'vat': rec.gst_number,
                    'supplier_rank': 1,
                    'comment': rec.notes,
                }
                if 'l10n_in_gst_treatment' in self.env['res.partner']._fields:
                    partner_vals['l10n_in_gst_treatment'] = rec.l10n_in_gst_treatment
                # Keep compatibility across Odoo variants where partner.mobile may not exist.
                if 'mobile' in self.env['res.partner']._fields:
                    partner_vals['mobile'] = rec.mobile
                partner = self.env['res.partner'].create(partner_vals)
            else:
                partner.supplier_rank = max(partner.supplier_rank, 1)

            # Ensure bulk-upload is enabled for freshly-approved vendors
            # (it defaults to True on new partners; this guards existing ones).
            if not partner.allow_bulk_upload:
                partner.allow_bulk_upload = True
                if (
                    'l10n_in_gst_treatment' in self.env['res.partner']._fields
                    and rec.l10n_in_gst_treatment
                ):
                    partner.l10n_in_gst_treatment = rec.l10n_in_gst_treatment

            # 2. Create portal user with random password
            password = self._generate_password()
            user = self.env['res.users'].search([('login', '=', rec.email)], limit=1)
            portal_group = self.env.ref('base.group_portal')
            if not user:
                user_vals = {
                    'name': rec.contact_name or rec.name,
                    'login': rec.email,
                    'email': rec.email,
                    'partner_id': partner.id,
                    'password': password,
                }
                if 'group_ids' in self.env['res.users']._fields:
                    user_vals['group_ids'] = [(6, 0, [portal_group.id])]
                elif 'groups_id' in self.env['res.users']._fields:
                    user_vals['groups_id'] = [(6, 0, [portal_group.id])]
                user = self.env['res.users'].create(user_vals)
            else:
                password = self._generate_password()
                user.password = password
                if 'group_ids' in self.env['res.users']._fields and portal_group not in user.group_ids:
                    user.write({'group_ids': [(4, portal_group.id)]})

            rec.write({
                'state': 'approved',
                'partner_id': partner.id,
                'user_id': user.id,
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            rec.message_post(
                body=_(
                    'Vendor request approved by %s.\n'
                    'Portal user: %s\n'
                    'Product registration link: %s'
                ) % (
                    self.env.user.name,
                    user.login,
                    rec._get_product_registration_url(),
                ),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

            # 3. Send approval mail with credentials
            template = self.env.ref(
                'vendor_registration.mail_template_vendor_approved_v2',
                raise_if_not_found=False,
            )
            if template:
                try:
                    template.with_context(
                        password=password,
                        product_registration_url=rec._get_product_registration_url(),
                    ).send_mail(rec.id, force_send=True)
                    rec.message_post(
                        body=_('Approval email sent to vendor email %s.') % rec.email,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )
                except Exception as exc:
                    rec.message_post(
                        body=_('Approval email could not be sent: %s') % exc,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )

    def action_reject(self):
        for rec in self:
            rec.write({'state': 'rejected'})

    def action_reset_draft(self):
        for rec in self:
            rec.write({'state': 'draft'})

    def action_open_partner(self):
        """Smart button: open the linked res.partner contact."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Contact',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_product_requests(self):
        """Smart button: open vendor product requests for this vendor."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vendor Product Requests',
            'res_model': 'vendor.product.request',
            'view_mode': 'list,form',
            'domain': [('vendor_registration_id', '=', self.id)],
            'context': {'default_vendor_registration_id': self.id},
        }

    @staticmethod
    def _generate_password(length=10):
        alphabet = string.ascii_letters + string.digits + '@#$!'
        return ''.join(secrets.choice(alphabet) for _ in range(length))
