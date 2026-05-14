# -*- coding: utf-8 -*-

import secrets
import string

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.addons.dgz_crm_orderlines.models.sale import (
    SaleOrder as DgzCrmSaleOrder,
    SaleOrderLine as DgzCrmSaleOrderLine,
)
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model
    def _is_product_requisition_module_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'product_requisition.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')

    def _get_requisition_orders(self):
        return self.filtered(
            lambda order: any(
                not line.display_type and line.product_id for line in order.order_line
            )
        )

    @api.model_create_multi
    def create(self, vals_list):
        Lead = self.env['crm.lead'].sudo()
        lead_ids = {
            vals.get('opportunity_id')
            for vals in vals_list
            if vals.get('opportunity_id')
        }
        first_quotation_lead_ids = set()
        if lead_ids:
            existing_groups = self.sudo().read_group(
                [('opportunity_id', 'in', list(lead_ids))],
                ['opportunity_id'],
                ['opportunity_id'],
            )
            existing_lead_ids = {
                group['opportunity_id'][0]
                for group in existing_groups
                if group.get('opportunity_id')
            }
            first_quotation_lead_ids = lead_ids - existing_lead_ids

        orders = super().create(vals_list)
        leads = Lead.browse(first_quotation_lead_ids).exists().filtered(lambda lead: lead.order_line_ids)

        if leads and hasattr(leads, '_send_requisition_portal_credentials_once'):
            leads._send_requisition_portal_credentials_once()

        return orders

    def action_confirm(self):
        if self._is_product_requisition_module_enabled():
            return super().action_confirm()

        for order in self:
            unapproved_products = ", ".join(
                line.product_id.name
                for line in order.order_line
                if line.product_id
                and line.product_id.state not in ('approved', 'mapped')
            )
            if unapproved_products:
                raise UserError(_(
                    "These Products are Not Approved or Mapped (%s) Please "
                    "Approve or Map all Products Before Confirming the Sale Order."
                ) % unapproved_products)

        return super(DgzCrmSaleOrder, self).action_confirm()

    def _apply_requisition_routes(self):
        if not self._is_product_requisition_module_enabled():
            return
        return super()._apply_requisition_routes()

    def _create_vendor_rfqs(self):
        if not self._is_product_requisition_module_enabled():
            return
        return super()._create_vendor_rfqs()


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    vendor_ids = fields.Many2many(
        domain="[('id', 'in', allowed_vendor_ids)]",
    )

    allowed_vendor_ids = fields.Many2many(
        'res.partner',
        compute='_compute_allowed_vendor_ids',
        string='Top Vendors',
    )

    def _get_top_product_vendors(self):
        self.ensure_one()
        sellers = self.product_id.seller_ids or self.product_template_id.seller_ids
        sellers = sellers.sorted(lambda seller: (seller.sequence, seller.id))
        return sellers[:3].mapped('partner_id')

    @api.depends('product_id', 'product_template_id')
    def _compute_allowed_vendor_ids(self):
        for line in self:
            if not self.env['sale.order']._is_product_requisition_module_enabled():
                line.allowed_vendor_ids = False
                continue
            line.allowed_vendor_ids = line._get_top_product_vendors()

    @api.onchange('product_id', 'product_template_id')
    def _onchange_product_vendor_domain(self):
        if not self.env['sale.order']._is_product_requisition_module_enabled():
            return {}

        for line in self:
            allowed_vendors = line.allowed_vendor_ids

            if line.vendor_ids:
                line.vendor_ids = line.vendor_ids & allowed_vendors
            line.rfq_vendor_ids = allowed_vendors

        return {
            'domain': {
                'vendor_ids': [('id', 'in', self.allowed_vendor_ids.ids)],
            }
        }

    def _action_launch_stock_rule(self, *, previous_product_uom_qty=False):
        if not self.env['sale.order']._is_product_requisition_module_enabled():
            return super(DgzCrmSaleOrderLine, self)._action_launch_stock_rule(
                previous_product_uom_qty=previous_product_uom_qty,
            )
        return super()._action_launch_stock_rule(
            previous_product_uom_qty=previous_product_uom_qty,
        )


class ResPartner(models.Model):
    _inherit = 'res.partner'

    requisition_portal_credentials_sent = fields.Boolean(
        string='Product Requisition Portal Credentials Sent',
        copy=False,
    )


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    @api.model
    def _is_product_requisition_module_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'product_requisition.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')

    def _generate_requisition_portal_password(self, length=10):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _index in range(length))

    def _get_requisition_portal_credentials_body(self, partner, email, password):
        self.ensure_one()
        return _(
            '<div style="font-family:Arial, sans-serif; font-size:14px; line-height:1.6; color:#333;">'
                '<p>Dear %(name)s,</p>'
                '<p>Your quotation has been created successfully. '
                'To help you review your quotation and future requisition updates, customer portal access has been enabled for you.</p>'
                '<p>Please use the login details below to access the portal.</p>'
                '<table style="border-collapse:collapse; margin:12px 0;">'
                    '<tr>'
                        '<td style="padding:6px 12px 6px 0;"><strong>Email</strong></td>'
                        '<td style="padding:6px 0;">%(email)s</td>'
                    '</tr>'
                    '<tr>'
                        '<td style="padding:6px 12px 6px 0;"><strong>Password</strong></td>'
                        '<td style="padding:6px 0;">%(password)s</td>'
                    '</tr>'
                '</table>'
                '<p>For security, please change your password after your first login.</p>'
                '<p>Regards,<br/>Product Requisition Team</p>'
            '</div>'
        ) % {
            'name': escape(partner.name or self.contact_name or email),
            'email': escape(email),
            'password': escape(password),
        }

    def _get_requisition_company_email_from(self):
        MailServer = self.env['ir.mail_server'].sudo()
        company = self.company_id or self.env.company
        email_from = (
            self.company_id.email_formatted
            or self.company_id.email
            or self.env.company.email_formatted
            or self.env.company.email
            or company.partner_id.email_formatted
            or company.partner_id.email
            or MailServer._get_default_from_address()
        )
        if email_from:
            return email_from

        mail_server = MailServer.search([], order='sequence, id', limit=1)
        if not mail_server:
            return False

        for value in (mail_server.from_filter, mail_server.smtp_user):
            for email_part in (value or '').split(','):
                email_part = email_part.strip()
                if '@' in email_part:
                    return email_part
        return False

    def _send_requisition_portal_credentials_once(self):
        if not self._is_product_requisition_module_enabled():
            return

        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)

        if not portal_group:
            return

        for lead in self:
            partner = lead.partner_id
            email = (partner.email or lead.email_from or '').strip().lower()

            if not partner or not email or partner.requisition_portal_credentials_sent:
                continue

            User = self.env['res.users'].sudo()
            user = User.search([
                ('login', '=', email)
            ], limit=1)

            if user:
                partner.sudo().requisition_portal_credentials_sent = True
                continue

            password = lead._generate_requisition_portal_password()
            user_vals = {
                'name': partner.name or lead.contact_name or email,
                'login': email,
                'email': email,
                'partner_id': partner.id,
                'password': password,
            }
            if 'group_ids' in User._fields:
                user_vals['group_ids'] = [(6, 0, [portal_group.id])]
            elif 'groups_id' in User._fields:
                user_vals['groups_id'] = [(6, 0, [portal_group.id])]
            user = User.create(user_vals)

            email_from = lead._get_requisition_company_email_from()

            if email_from:
                subject = _('Your Portal Login Details')
                body = lead._get_requisition_portal_credentials_body(partner, email, password)
                mail_values = {
                    'subject': subject,
                    'email_from': email_from,
                    'email_to': email,
                    'outgoing_email_to': email,
                    'model': lead._name,
                    'res_id': lead.id,
                    'auto_delete': False,
                    'body_html': body,
                }
                self.env['mail.mail'].sudo().create(mail_values).send(raise_exception=True)

                lead.message_post(
                    body=Markup(body),
                    subject=subject,
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment',
                )

            partner.sudo().requisition_portal_credentials_sent = True


class CrmLeadProducts(models.Model):
    _inherit = 'crm.lead.products'

    product_category = fields.Selection([
        ('goods', 'Goods'),
        ('service', 'Service'),
    ], string='Product Category', default='goods')

    asset_category_id = fields.Many2one(
        'product.public.category',
        string='Asset Category',
    )

    product_status = fields.Selection(
        related='product_id.state',
        string='Status',
        readonly=True,
    )

    uom_text = fields.Char(string='UOM')

    lead_time = fields.Integer(string='Lead Time')

    budget = fields.Float(string='Budget')

    expected_date = fields.Date(string='Expected Date')
