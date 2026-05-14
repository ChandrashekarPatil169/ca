# -*- coding: utf-8 -*-

import hmac
import hashlib
import logging
import random
import re
import time

from markupsafe import escape

from odoo import _, http, fields
from odoo.http import request
from werkzeug.exceptions import BadRequest
from werkzeug.utils import redirect


_logger = logging.getLogger(__name__)


class ProductRequisitionController(http.Controller):
    OTP_SESSION_KEY = 'product_requisition_otp'
    OTP_TTL_SECONDS = 10 * 60

    def _is_module_enabled(self):
        value = request.env['ir.config_parameter'].sudo().get_param(
            'product_requisition.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')

    def _module_disabled_response(self):
        return request.render(
            'website.404',
            {'path': request.httprequest.path},
            status=404,
        )

    def _get_products(self):
        """Return sale-able products for the website requisition picker."""
        return request.env['product.product'].sudo().search([
            ('active', '=', True),
            ('sale_ok', '=', True),
            ('state', '=', 'approved'),
        ], order='name')

    def _get_public_category_filter_ids(self, categories):
        category_ids = set()
        for category in categories:
            current = category
            while current:
                category_ids.add(current.id)
                current = current.parent_id
        return category_ids

    def _get_asset_categories(self):
        return request.env['product.public.category'].sudo().search([], order='sequence, name, id')

    def _get_asset_category_filter_ids(self, product):
        category_ids = set()
        category_ids.update(self._get_public_category_filter_ids(product.product_tmpl_id.public_categ_ids))
        return category_ids

    def _get_company_email_from(self):
        company = (request.website.sudo().company_id or request.env.company).sudo()
        MailServer = request.env['ir.mail_server'].sudo()
        email_from = (
            company.email_formatted
            or company.email
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

    def _get_requisition_catalog(self):
        categories = self._get_asset_categories()
        products = self._get_products()
        return {
            'categories': [{
                'id': category.id,
                'name': category.display_name,
            } for category in categories],
            'products': [{
                'id': product.id,
                'name': product.display_name,
                'product_category': 'service' if product.type == 'service' else 'goods',
                'asset_category_ids': list(self._get_asset_category_filter_ids(product)),
                'uom': product.uom_id.name or '',
                'price': product.lst_price or 0.0,
            } for product in products],
        }

    def _allow_bulk_upload(self, partner):
        if not partner:
            return False
        if 'allow_bulk_upload' in partner._fields:
            return bool(partner.allow_bulk_upload)
        return True

    def _prepare_values(self, error=None, form_values=None, lead=None, success=None):
        partner = request.env.user.partner_id if not request.env.user._is_public() else False
        products = self._get_products()
        product_prices = {p.id: p.lst_price for p in products}
        product_asset_category_ids = {
            p.id: ','.join(
                str(category_id)
                for category_id in self._get_asset_category_filter_ids(p)
            )
            for p in products
        }
        CrmLead = request.env['crm.lead'].sudo()
        form_values = form_values or {}
        logged_in_user = bool(partner)
        portal_customer_verified = self._is_portal_customer_verified(partner)
        otp_verified = logged_in_user or portal_customer_verified or self._is_otp_verified(
            form_values.get('email'),
            form_values.get('otp_token'),
        )
        return {
            'page_name': 'product_requisition',
            'products': products,
            'product_prices': product_prices,
            'product_public_category_ids': product_asset_category_ids,
            'asset_categories': self._get_asset_categories(),
            'countries': request.env['res.country'].sudo().search([], order='name'),
            'states': request.env['res.country.state'].sudo().search([], order='name'),
            'tags': request.env['crm.tag'].sudo().search([], order='name'),
            'priorities': CrmLead._fields['priority'].selection,
            'partner': partner,
            'error': error,
            'success': success,
            'form_values': form_values,
            'lead': lead,
            'otp_verified': otp_verified,
            'otp_required': not logged_in_user,
            'allow_bulk_upload': self._allow_bulk_upload(partner),
        }

    def _is_valid_email(self, email):
        return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email or ''))

    def _is_portal_customer_verified(self, partner):
        if not partner or not partner.requisition_portal_credentials_sent:
            return False
        partner_email = (partner.email or '').strip().lower()
        user_login = (request.env.user.login or '').strip().lower()
        return bool(partner_email and partner_email == user_login)

    def _get_otp_token_secret(self):
        return (
            request.env['ir.config_parameter'].sudo().get_param('database.secret')
            or request.env.cr.dbname
        )

    def _make_otp_verification_token(self, email, expires_at):
        email = (email or '').strip().lower()
        expires_at = int(expires_at or 0)
        payload = '%s:%s' % (email, expires_at)
        signature = hmac.new(
            self._get_otp_token_secret().encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        return '%s:%s' % (payload, signature)

    def _is_valid_otp_verification_token(self, email, token):
        email = (email or '').strip().lower()
        parts = (token or '').split(':')
        if len(parts) != 3:
            return False
        token_email, raw_expires_at, signature = parts
        if token_email != email:
            return False
        try:
            expires_at = int(raw_expires_at)
        except ValueError:
            return False
        if expires_at < time.time():
            return False
        expected = self._make_otp_verification_token(token_email, expires_at)
        return hmac.compare_digest(token, expected)

    def _is_otp_verified(self, email=None, token=None):
        if token and self._is_valid_otp_verification_token(email, token):
            return True
        data = request.session.get(self.OTP_SESSION_KEY) or {}
        if not data.get('verified'):
            return False
        if email and data.get('email') != email:
            return False
        return data.get('expires_at', 0) >= time.time()

    def _verify_submitted_otp(self, email=None, otp=None):
        email = (email or '').strip().lower()
        otp = (otp or '').strip()
        data = request.session.get(self.OTP_SESSION_KEY) or {}
        if not email or not otp:
            return False
        if not data or data.get('email') != email:
            return False
        if data.get('expires_at', 0) < time.time():
            return False
        if data.get('otp') != otp:
            return False
        data['verified'] = True
        request.session[self.OTP_SESSION_KEY] = data
        return True

    def _send_otp_email(self, name, email, otp):
        email_from = self._get_company_email_from()
        if not email_from:
            raise BadRequest('No sender email address is configured in Odoo.')

        safe_name = escape(name or email)
        safe_otp = escape(otp)
        mail = request.env['mail.mail'].sudo().create({
            'subject': _('Your Product Requisition Verification Code'),
            'email_from': email_from,
            'email_to': email,
            'auto_delete': False,
            'body_html': _(
                '<div style="font-family:Arial, sans-serif; font-size:14px; line-height:1.6; color:#333;">'
                    '<p>Dear %(name)s,</p>'
                    '<p>Thank you for starting your product requisition. '
                    'Please use the verification code below to confirm your email address.</p>'
                    '<p style="font-size:20px; font-weight:700; letter-spacing:2px; margin:16px 0;">%(otp)s</p>'
                    '<p>This code is valid for 10 minutes. If you did not request this code, please ignore this email.</p>'
                    '<p>Regards,<br/>Product Requisition Team</p>'
                '</div>'
            ) % {
                'name': safe_name,
                'otp': safe_otp,
            },
        })
        mail.send(raise_exception=True)

    def _send_requisition_confirmation_email(self, lead, email_to=None):
        email_to = (email_to or lead.email_from or lead.partner_id.email or '').strip()
        email_from = self._get_company_email_from()
        if not email_to or not email_from:
            _logger.warning(
                'Product requisition confirmation email skipped for lead %s: missing recipient or sender.',
                lead.id,
            )
            return False

        product_lines = '<br/>'.join(
            '%s | Qty: %s' % (
                escape(line.product_id.display_name),
                escape(line.product_uom_qty),
            )
            for line in lead.order_line_ids
        )
        safe_name = escape(lead.contact_name or lead.partner_id.name or email_to)
        safe_reference = escape(lead.name)
        safe_serial = escape(lead.id)
        subject = _('Product Requisition Submitted - %s') % lead.name
        body_html = _(
            '<div style="font-family:Arial, sans-serif; font-size:14px; line-height:1.6; color:#333;">'
                '<p>Dear %(name)s,</p>'
                '<p>Thank you for submitting your product requisition. '
                'Your request has been received successfully, and our team will review the details and contact you shortly.</p>'
                '<p><strong>Reference:</strong> %(reference)s<br/>'
                '<strong>Serial No.:</strong> %(serial)s</p>'
                '<p><strong>Submitted Products:</strong><br/>%(product_lines)s</p>'
                '<p>We appreciate your request and will keep you informed about the next steps.</p>'
                '<p>Regards,<br/>Product Requisition Team</p>'
            '</div>'
        ) % {
            'name': safe_name,
            'reference': safe_reference,
            'serial': safe_serial,
            'product_lines': product_lines,
        }
        mail = request.env['mail.mail'].sudo().create({
            'subject': subject,
            'email_from': email_from,
            'email_to': email_to,
            'auto_delete': False,
            'body_html': body_html,
        })
        try:
            mail.send(raise_exception=True)
            _logger.info(
                'Product requisition confirmation email sent for lead %s to %s.',
                lead.id,
                email_to,
            )
        except Exception as exc:
            _logger.warning(
                'Product requisition confirmation email could not be sent for lead %s: %s',
                lead.id,
                exc,
            )
            lead.sudo().message_post(
                body=_('Confirmation email could not be sent: %s') % exc,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
            return False
        return True

    @http.route(
        '/product-requisition/send-otp',
        type='jsonrpc',
        auth='public',
        website=True,
        methods=['POST'],
    )
    def product_requisition_send_otp(self, name=None, email=None, code=None):
        if not self._is_module_enabled():
            return {'ok': False, 'message': _('Product requisition is currently disabled.')}
        email = (email or '').strip().lower()
        name = (name or '').strip()
        code = (code or '').strip()

        if not name:
            return {'ok': False, 'message': _('Name is required.')}
        if not self._is_valid_email(email):
            return {'ok': False, 'message': _('Please enter a valid email address.')}
        otp = f'{random.SystemRandom().randint(100000, 999999)}'
        request.session[self.OTP_SESSION_KEY] = {
            'email': email,
            'otp': otp,
            'verified': False,
            'expires_at': time.time() + self.OTP_TTL_SECONDS,
        }
        try:
            self._send_otp_email(name, email, otp)
        except Exception as exc:
            request.env.cr.rollback()
            return {'ok': False, 'message': _('OTP email could not be sent: %s') % str(exc)}
        return {'ok': True, 'message': _('OTP sent to %s.', email)}

    @http.route(
        '/product-requisition/verify-otp',
        type='jsonrpc',
        auth='public',
        website=True,
        methods=['POST'],
    )
    def product_requisition_verify_otp(self, email=None, otp=None):
        if not self._is_module_enabled():
            return {'ok': False, 'message': _('Product requisition is currently disabled.')}
        email = (email or '').strip().lower()
        otp = (otp or '').strip()
        data = request.session.get(self.OTP_SESSION_KEY) or {}

        if not data or data.get('email') != email:
            return {'ok': False, 'message': _('Please send an OTP to this email first.')}
        if data.get('expires_at', 0) < time.time():
            return {'ok': False, 'message': _('OTP expired. Please resend OTP.')}
        if data.get('otp') != otp:
            return {'ok': False, 'message': _('Incorrect OTP. Please enter again. If not received yet, please restart the chat.')}

        data['verified'] = True
        request.session[self.OTP_SESSION_KEY] = data
        return {
            'ok': True,
            'message': _('Email verified. You can now add products.'),
            'token': self._make_otp_verification_token(email, data.get('expires_at')),
        }

    @http.route(
        '/product-requisition/session-status',
        type='jsonrpc',
        auth='public',
        website=True,
        methods=['POST'],
    )
    def product_requisition_session_status(self):
        if not self._is_module_enabled():
            return {'authenticated': False, 'name': '', 'email': ''}
        partner = request.env.user.partner_id if not request.env.user._is_public() else False
        return {
            'authenticated': bool(partner),
            'name': partner.name if partner else '',
            'email': partner.email if partner else '',
        }

    @http.route(
        '/product-requisition/asset-categories',
        type='jsonrpc',
        auth='public',
        website=True,
        methods=['POST'],
    )
    def product_requisition_asset_categories(self):
        if not self._is_module_enabled():
            return []
        return self._get_requisition_catalog()['categories']

    @http.route(
        '/product-requisition/catalog',
        type='jsonrpc',
        auth='public',
        website=True,
        methods=['POST'],
    )
    def product_requisition_catalog(self):
        if not self._is_module_enabled():
            return {'categories': [], 'products': []}
        return self._get_requisition_catalog()

    def _get_record_from_form(self, model_name, raw_id, domain=None):
        if not raw_id:
            return request.env[model_name].sudo()
        try:
            record_id = int(raw_id)
        except ValueError as exc:
            raise BadRequest('Invalid form value.') from exc
        domain = [('id', '=', record_id)] + (domain or [])
        return request.env[model_name].sudo().search(domain, limit=1)

    def _get_requisition_history_domain(self):
        partner = request.env.user.partner_id
        commercial_partner = partner.commercial_partner_id
        return [
            ('partner_id', 'child_of', commercial_partner.id),
            ('order_line_ids', '!=', False),
        ]

    @http.route(
        ['/product-requisition', '/my/product-requisition'],
        type='http', auth='public', website=True,
    )
    def product_requisition(self, **kw):
        if not self._is_module_enabled():
            return self._module_disabled_response()
        if request.env.user._is_public():
            request.session.pop(self.OTP_SESSION_KEY, None)
        return request.render(
            'product_requisition.product_requisition_form',
            self._prepare_values(success=kw.get('success'), error=kw.get('error')),
        )

    @http.route(
        '/my/product-requisition/history',
        type='http', auth='user', website=True,
    )
    def product_requisition_history(self, **kw):
        if not self._is_module_enabled():
            return self._module_disabled_response()
        if request.env.user._is_public():
            return redirect('/web/login?redirect=/my/product-requisition/history')

        CrmLead = request.env['crm.lead'].sudo()
        requisitions = CrmLead.search(
            self._get_requisition_history_domain(),
            order='create_date desc, id desc',
        )
        priority_labels = dict(CrmLead._fields['priority'].selection)
        return request.render(
            'product_requisition.product_requisition_history',
            {
                'page_name': 'product_requisition_history',
                'requisitions': requisitions,
                'priority_labels': priority_labels,
            },
        )

    @http.route(
        '/my/product-requisition/template',
        type='http',
        auth='user',
        website=True,
    )
    def download_product_requisition_template(self, **kw):
        if not self._is_module_enabled():
            return self._module_disabled_response()

        import io
        import pandas as pd

        template_type = (kw.get('type') or 'all').lower()
        if template_type == 'service':
            columns = [
                'product_category',
                'asset_category',
                'product_name',
                'budget',
                'expected_date',
                'description',
            ]
            sample = [{
                'product_category': 'service',
                'asset_category': '',
                'product_name': '',
                'budget': 0,
                'expected_date': '',
                'description': '',
            }]
            sheet_name = 'Services'
            filename = 'product_requisition_service_template.xlsx'
        elif template_type == 'goods':
            columns = [
                'product_category',
                'asset_category',
                'product_name',
                'quantity',
                'uom',
                'lead_time',
                'budget',
                'description',
            ]
            sample = [{
                'product_category': 'goods',
                'asset_category': '',
                'product_name': '',
                'quantity': 1,
                'uom': '',
                'lead_time': 0,
                'budget': 0,
                'description': '',
            }]
            sheet_name = 'Goods'
            filename = 'product_requisition_goods_template.xlsx'
        else:
            columns = [
                'product_category',
                'asset_category',
                'product_name',
                'quantity',
                'uom',
                'lead_time',
                'budget',
                'expected_date',
                'description',
            ]
            sample = [{
                'product_category': 'goods',
                'asset_category': '',
                'product_name': '',
                'quantity': 1,
                'uom': '',
                'lead_time': 0,
                'budget': 0,
                'expected_date': '',
                'description': '',
            }, {
                'product_category': 'service',
                'asset_category': '',
                'product_name': '',
                'quantity': '',
                'uom': '',
                'lead_time': '',
                'budget': 0,
                'expected_date': '',
                'description': '',
            }]
            sheet_name = 'Requisition Lines'
            filename = 'product_requisition_template.xlsx'

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame(sample, columns=columns).to_excel(
                writer,
                index=False,
                sheet_name=sheet_name,
            )
        output.seek(0)

        return request.make_response(
            output.read(),
            headers=[
                (
                    'Content-Type',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                ),
                (
                    'Content-Disposition',
                    'attachment; filename=%s' % filename,
                ),
            ],
        )

    @http.route(
        '/my/product-requisition/bulk-upload',
        type='http',
        auth='user',
        website=True,
        methods=['POST'],
    )
    def product_requisition_bulk_upload(self, **post):
        if not self._is_module_enabled():
            return self._module_disabled_response()

        import io
        import pandas as pd

        partner = request.env.user.partner_id
        if not self._allow_bulk_upload(partner):
            return redirect('/my/product-requisition?error=Bulk+upload+is+not+enabled+for+your+contact')

        uploaded_file = request.httprequest.files.get('requisition_file')
        if not uploaded_file:
            return redirect('/my/product-requisition?error=No+file+uploaded')

        try:
            filename = (uploaded_file.filename or '').lower()
            file_content = uploaded_file.read()
            if filename.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(file_content))
            else:
                df = pd.read_excel(io.BytesIO(file_content), engine='openpyxl')
        except Exception:
            return redirect('/my/product-requisition?error=Invalid+Excel+file')

        def clean_string(value):
            if pd.isna(value):
                return ''
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            value = str(value).strip()
            if value.endswith('.0') and value[:-2].isdigit():
                return value[:-2]
            return value

        def clean_float(value, default=0.0):
            try:
                if pd.isna(value):
                    return default
                return float(value)
            except Exception:
                return default

        def clean_int(value, default=0):
            try:
                if pd.isna(value):
                    return default
                return int(float(value))
            except Exception:
                return default

        def clean_date(value):
            if pd.isna(value):
                return False
            try:
                return fields.Date.to_date(value)
            except Exception:
                return False

        def find_asset_category(value):
            value = clean_string(value)
            if not value:
                return request.env['product.public.category'].sudo()
            Category = request.env['product.public.category'].sudo()
            if value.isdigit():
                category = Category.browse(int(value)).exists()
                if category:
                    return category
            return Category.search([('name', '=ilike', value)], limit=1)

        def find_allowed_product(product_name, product_category):
            product_name = clean_string(product_name)
            if not product_name:
                return request.env['product.product'].sudo()
            product_type = 'service' if product_category == 'service' else 'consu'
            return request.env['product.product'].sudo().search([
                ('active', '=', True),
                ('sale_ok', '=', True),
                ('state', '=', 'approved'),
                ('type', '=', product_type),
                ('name', '=ilike', product_name),
            ], limit=1)

        lines = []
        created_count = 0

        for _row_index, row in df.iterrows():
            product_name = clean_string(row.get('product_name'))
            if not product_name:
                continue

            product_category = clean_string(row.get('product_category') or row.get('type')).lower()
            if product_category not in ('goods', 'service'):
                product_category = 'goods'

            asset_category = find_asset_category(row.get('asset_category') or row.get('asset_category_id'))
            product = find_allowed_product(product_name, product_category)
            if not product:
                product_values = {
                    'name': product_name,
                    'sale_ok': True,
                    'purchase_ok': True,
                    'type': 'service' if product_category == 'service' else 'consu',
                    'state': 'draft',
                }
                if asset_category:
                    product_values['public_categ_ids'] = [fields.Command.set(asset_category.ids)]
                product = request.env['product.product'].sudo().create(product_values)

            quantity = clean_float(row.get('quantity'), 1.0)
            if quantity <= 0:
                quantity = 1.0
            description = clean_string(row.get('description')) or product.display_name

            lines.append(fields.Command.create({
                'product_id': product.id,
                'name': description,
                'product_category': product_category,
                'asset_category_id': asset_category.id if asset_category else False,
                'product_uom_qty': quantity,
                'uom_text': clean_string(row.get('uom')),
                'lead_time': max(clean_int(row.get('lead_time'), 0), 0),
                'budget': max(clean_float(row.get('budget'), 0.0), 0.0),
                'expected_date': clean_date(row.get('expected_date')),
                'price_unit': product.lst_price,
            }))
            created_count += 1

        if not lines:
            return redirect('/my/product-requisition?error=No+valid+product+rows+found')

        lead_name = request.env['ir.sequence'].sudo().next_by_code('product.requisition.lead') or _(
            'Product Requisition - %s'
        ) % partner.name
        lead = request.env['crm.lead'].sudo().create({
            'name': lead_name,
            'type': 'opportunity',
            'contact_name': partner.name,
            'partner_name': partner.company_name,
            'partner_id': partner.id,
            'email_from': partner.email,
            'phone': partner.phone or getattr(partner, 'mobile', False) or '',
            'website': partner.website,
            'street': partner.street,
            'street2': partner.street2,
            'city': partner.city,
            'zip': partner.zip,
            'state_id': partner.state_id.id if partner.state_id else False,
            'country_id': partner.country_id.id if partner.country_id else False,
            'description': _('Created from product requisition bulk upload.'),
            'order_line_ids': lines,
        })
        try:
            self._send_requisition_confirmation_email(lead, partner.email)
        except Exception:
            _logger.exception("Product requisition confirmation email could not be sent for lead %s.", lead.id)

        return redirect(
            '/my/product-requisition?success=%s+products+uploaded+successfully' % created_count
        )

    @http.route(
        '/product-requisition/submit',
        type='http', auth='public', website=True, methods=['POST'],
    )
    def product_requisition_submit(self, **kw):
        if not self._is_module_enabled():
            return self._module_disabled_response()
        form = request.httprequest.form
        partner = request.env.user.partner_id if not request.env.user._is_public() else False

        customer_name = (form.get('customer_name') or '').strip()
        lead_name     = (form.get('lead_name') or '').strip()
        email         = (form.get('email') or '').strip().lower()
        otp_token     = (form.get('otp_token') or '').strip()
        otp_code      = (form.get('otp') or '').strip()
        employee_code = (form.get('employee_code') or '').strip()
        email_cc      = (form.get('email_cc') or '').strip()
        phone         = (form.get('phone') or '').strip()
        company_name  = (form.get('company_name') or '').strip()
        job_position  = (form.get('job_position') or '').strip()
        website       = (form.get('website') or '').strip()
        street        = (form.get('street') or '').strip()
        street2       = (form.get('street2') or '').strip()
        city          = (form.get('city') or '').strip()
        zip_code      = (form.get('zip') or '').strip()
        priority      = (form.get('priority') or '0').strip()
        notes         = (form.get('notes') or '').strip()
        country       = self._get_record_from_form('res.country', form.get('country_id'))
        state_domain  = [('country_id', '=', country.id)] if country else []
        state         = self._get_record_from_form('res.country.state', form.get('state_id'), state_domain)
        tag_ids = []
        for raw_tag_id in form.getlist('tag_ids'):
            tag = self._get_record_from_form('crm.tag', raw_tag_id)
            if tag:
                tag_ids.append(tag.id)

        if partner:
            customer_name = customer_name or partner.name
            email         = email or partner.email or ''
            phone = phone or partner.phone or getattr(partner, 'mobile', False) or ''
            company_name  = company_name or partner.company_name or ''
            job_position  = job_position or partner.function or ''
            website       = website or partner.website or ''
            street        = street or partner.street or ''
            street2       = street2 or partner.street2 or ''
            city          = city or partner.city or ''
            zip_code      = zip_code or partner.zip or ''
            country       = country or partner.country_id
            state         = state or partner.state_id
        logged_in_user = bool(partner)
        if logged_in_user and not employee_code:
            employee_code = partner.ref or str(partner.id)
        portal_customer_verified = (
            self._is_portal_customer_verified(partner)
            and (partner.email or '').strip().lower() == email
        )

        form_values = {
            'lead_name': lead_name,
            'customer_name': customer_name,
            'email': email,
            'otp_token': otp_token,
            'otp': otp_code,
            'employee_code': employee_code,
            'email_cc': email_cc,
            'phone': phone,
            'company_name': company_name,
            'job_position': job_position,
            'website': website,
            'street': street,
            'street2': street2,
            'city': city,
            'zip': zip_code,
            'country_id': country.id if country else False,
            'state_id': state.id if state else False,
            'priority': priority,
            'tag_ids': tag_ids,
            'notes': notes,
        }

        if not customer_name:
            return request.render(
                'product_requisition.product_requisition_form',
                self._prepare_values(_('Customer name is required.'), form_values),
            )
        if (
            not logged_in_user
            and
            not portal_customer_verified
            and
            not self._is_otp_verified(email, otp_token)
            and not self._verify_submitted_otp(email, otp_code)
        ):
            return request.render(
                'product_requisition.product_requisition_form',
                self._prepare_values(_('Please verify your email with OTP before submitting.'), form_values),
            )
        if not lead_name:
            lead_name = request.env['ir.sequence'].sudo().next_by_code('product.requisition.lead') or _('Product Requisition - %s') % customer_name

        product_ids  = form.getlist('product_id')
        product_names = form.getlist('product_name')
        product_categories = form.getlist('product_category')
        asset_categories = form.getlist('asset_category_id')
        quantities   = form.getlist('quantity')
        descriptions = form.getlist('description')
        uoms = form.getlist('uom')
        lead_times = form.getlist('lead_time')
        budgets = form.getlist('budget')
        expected_dates = form.getlist('expected_date')

        allowed_products    = self._get_products()
        allowed_product_ids = set(allowed_products.ids)
        lines = []

        line_count = max(
            len(product_ids),
            len(product_names),
            len(product_categories),
            len(asset_categories),
            len(quantities),
            len(descriptions),
            len(uoms),
            len(lead_times),
            len(budgets),
            len(expected_dates),
        )

        for index in range(line_count):
            raw_pid = product_ids[index].strip() if index < len(product_ids) and product_ids[index] else ''
            raw_name = product_names[index].strip() if index < len(product_names) and product_names[index] else ''
            product_category = product_categories[index].strip() if index < len(product_categories) and product_categories[index] else 'goods'
            raw_asset_category = asset_categories[index].strip() if index < len(asset_categories) and asset_categories[index] else ''
            product = request.env['product.product'].sudo()
            asset_category = self._get_record_from_form('product.public.category', raw_asset_category)
            if raw_pid:
                try:
                    product_id = int(raw_pid)
                except ValueError as exc:
                    raise BadRequest('Invalid product selected.') from exc

                if product_id not in allowed_product_ids:
                    raise BadRequest('The selected product is not available for requisitions.')
                product = allowed_products.filtered(lambda r, pid=product_id: r.id == pid)[:1]
                if product_category == 'service' and product.type != 'service':
                    raise BadRequest('Please select a service product.')
                if product_category == 'goods':
                    if product.type == 'service':
                        raise BadRequest('Please select a goods product.')
                if asset_category and asset_category.id not in self._get_asset_category_filter_ids(product):
                    raise BadRequest('Please select a product from the chosen asset category.')
            elif raw_name:
                product_values = {
                    'name': raw_name,
                    'sale_ok': True,
                    'purchase_ok': True,
                    'type': 'service' if product_category == 'service' else 'consu',
                    'state': 'draft',
                }
                if asset_category:
                    product_values['public_categ_ids'] = [fields.Command.set(asset_category.ids)]
                product = request.env['product.product'].sudo().create(product_values)
            else:
                continue

            try:
                quantity = float(quantities[index]) if index < len(quantities) and quantities[index] else 1.0
            except ValueError:
                quantity = 1.0
            if quantity <= 0:
                quantity = 1.0

            raw_desc = descriptions[index].strip() if index < len(descriptions) and descriptions[index] else ''
            if not raw_desc:
                if hasattr(product, 'get_product_multiline_description_sale'):
                    raw_desc = product.get_product_multiline_description_sale()
                else:
                    raw_desc = product.display_name

            try:
                lead_time = int(lead_times[index]) if index < len(lead_times) and lead_times[index] else 0
            except ValueError:
                lead_time = 0
            try:
                budget = float(budgets[index]) if index < len(budgets) and budgets[index] else 0.0
            except ValueError:
                budget = 0.0
            try:
                expected_date = fields.Date.to_date(expected_dates[index]) if index < len(expected_dates) and expected_dates[index] else False
            except ValueError:
                expected_date = False

            lines.append(fields.Command.create({
                'product_id': product.id,
                'name': raw_desc,
                'product_category': product_category if product_category in ('goods', 'service') else 'goods',
                'asset_category_id': asset_category.id if asset_category else False,
                'product_uom_qty': quantity,
                'uom_text': uoms[index].strip() if index < len(uoms) and uoms[index] else '',
                'lead_time': max(lead_time, 0),
                'budget': max(budget, 0.0),
                'expected_date': expected_date,
                'price_unit': product.lst_price,
            }))

        if not lines:
            return request.render(
                'product_requisition.product_requisition_form',
                self._prepare_values(_('Please select at least one product.'), form_values),
            )

        form_partner = partner
        existing_customer = False
        existing_user = request.env['res.users'].sudo()
        email_partner = request.env['res.partner'].sudo()
        if email:
            existing_user = request.env['res.users'].sudo().search([('login', '=', email)], limit=1)
            existing_customer = existing_customer or bool(existing_user)
            email_partner = request.env['res.partner'].sudo().search(
                [('email', '=', email)], limit=1,
            )
            existing_customer = existing_customer or bool(email_partner)
        if email_partner:
            partner = email_partner
        elif form_partner and (not email or (form_partner.email or '').strip().lower() == email):
            partner = form_partner
            existing_customer = True
        else:
            partner = request.env['res.partner'].sudo()
        if not partner:
            partner = request.env['res.partner'].sudo().create({
                'name': customer_name,
                'email': email,
                'ref': employee_code,
                'phone': phone,
                'company_name': company_name,
                'function': job_position,
                'website': website,
                'street': street,
                'street2': street2,
                'city': city,
                'zip': zip_code,
                'state_id': state.id if state else False,
                'country_id': country.id if country else False,
            })

        lead_values = {
            'name': lead_name,
            'type': 'opportunity' if existing_customer else 'lead',
            'contact_name': customer_name,
            'partner_name': company_name,
            'partner_id': partner.id,
            'email_from': email,
            'email_cc': email_cc,
            'function': job_position,
            'phone': phone,
            'website': website,
            'street': street,
            'street2': street2,
            'city': city,
            'zip': zip_code,
            'state_id': state.id if state else False,
            'country_id': country.id if country else False,
            'priority': priority if priority in {'0', '1', '2', '3'} else '0',
            'description': '\n'.join(filter(None, [
                notes,
                employee_code and _('Code: %s') % employee_code,
            ])),
            'order_line_ids': lines,
        }
        if tag_ids:
            lead_values['tag_ids'] = [fields.Command.set(tag_ids)]
        lead = request.env['crm.lead'].sudo().create(lead_values)
        try:
            self._send_requisition_confirmation_email(lead, email or partner.email)
        except Exception:
            _logger.exception("Product requisition confirmation email could not be sent for lead %s.", lead.id)

        return request.render(
            'product_requisition.product_requisition_success',
            self._prepare_values(lead=lead),
        )
