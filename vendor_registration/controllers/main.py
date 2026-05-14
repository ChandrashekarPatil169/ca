# -*- coding: utf-8 -*-

from odoo import _, http, fields
from odoo.http import request
from werkzeug.utils import redirect
import json
import urllib.error
import urllib.parse
import urllib.request


class VendorRegistrationController(http.Controller):

    def _is_module_enabled(self):
        value = request.env['ir.config_parameter'].sudo().get_param(
            'vendor_registration.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')

    def _module_disabled_response(self):
        return request.render(
            'website.404',
            {'path': request.httprequest.path},
            status=404,
        )

    def _find_existing_product_template(self, product_name):
        if not product_name:
            return request.env['product.template'].sudo()
        return request.env['product.template'].sudo().search([
            ('name', '=ilike', product_name),
            ('active', '=', True),
            ('purchase_ok', '=', True),
        ], limit=1)

    @http.route(
        '/vendor-portal-access',
        type='http', auth='public', website=True,
    )
    def vendor_portal_access(self, **kw):
        if request.env.user._is_public():
            return redirect('/web/login')
        return redirect('/web')

    # ── Registration Form ────────────────────────────────────────────────────

    def _prepare_registration_values(self, error=None, form_values=None, success=False):
        return {
            'page_name': 'vendor_registration',
            'countries': request.env['res.country'].sudo().search([], order='name'),
            'states': request.env['res.country.state'].sudo().search([], order='name'),
            'error': error,
            'form_values': form_values or {},
            'success': success,
        }

    @http.route(
        ['/vendor-registration'],
        type='http', auth='public', website=True,
    )
    def vendor_registration_form(self, **kw):
        if not self._is_module_enabled():
            return self._module_disabled_response()
        return request.render(
            'vendor_registration.vendor_registration_form',
            self._prepare_registration_values(),
        )

    @http.route(
        '/vendor-registration/gst-lookup',
        type='jsonrpc',
        auth='public',
        website=True,
        methods=['POST'],
    )
    def vendor_registration_gst_lookup(self, gstin=None):
        if not self._is_module_enabled():
            return {'error': _('Vendor registration is currently disabled.')}
        gstin = (gstin or '').strip().upper()

        if len(gstin) != 15:
            return {'error': _('GST Number must be exactly 15 characters.')}

        result = self._get_gstin_derived_details(gstin)
        provider_details = (
            self._fetch_gstin_odoo_partner_autocomplete_details(gstin)
            or self._fetch_gstin_provider_details(gstin)
        )

        if provider_details:
            result.update(provider_details)

        return result

    @http.route(
        '/vendor-registration/session-status',
        type='jsonrpc',
        auth='public',
        website=True,
        methods=['POST'],
    )
    def vendor_registration_session_status(self):
        if not self._is_module_enabled():
            return {'authenticated': False, 'name': '', 'email': ''}
        partner = request.env.user.partner_id if not request.env.user._is_public() else False
        return {
            'authenticated': bool(partner),
            'name': partner.name if partner else '',
            'email': partner.email if partner else '',
        }

    def _get_gstin_derived_details(self, gstin):
        state_code = gstin[:2]
        pan = gstin[2:12]
        pan_type = pan[3:4]
        state_by_code = {
            '01': 'Jammu and Kashmir', '02': 'Himachal Pradesh',
            '03': 'Punjab', '04': 'Chandigarh', '05': 'Uttarakhand',
            '06': 'Haryana', '07': 'Delhi', '08': 'Rajasthan',
            '09': 'Uttar Pradesh', '10': 'Bihar', '11': 'Sikkim',
            '12': 'Arunachal Pradesh', '13': 'Nagaland',
            '14': 'Manipur', '15': 'Mizoram', '16': 'Tripura',
            '17': 'Meghalaya', '18': 'Assam', '19': 'West Bengal',
            '20': 'Jharkhand', '21': 'Odisha', '22': 'Chhattisgarh',
            '23': 'Madhya Pradesh', '24': 'Gujarat',
            '26': 'Dadra and Nagar Haveli and Daman and Diu',
            '27': 'Maharashtra', '29': 'Karnataka', '30': 'Goa',
            '31': 'Lakshadweep', '32': 'Kerala', '33': 'Tamil Nadu',
            '34': 'Puducherry', '35': 'Andaman and Nicobar Islands',
            '36': 'Telangana', '37': 'Andhra Pradesh', '38': 'Ladakh',
        }
        company_type_by_pan = {
            'P': 'individual',
            'F': 'partnership',
            'L': 'llp',
            'C': 'private_ltd',
        }

        return {
            'gst_number': gstin,
            'pan_number': pan,
            'state_name': state_by_code.get(state_code, ''),
            'country_name': 'India',
            'company_type': company_type_by_pan.get(pan_type, 'other'),
            'l10n_in_gst_treatment': 'regular' if pan else 'unregistered',
            'gst_registration_number': gstin[12:13],
        }

    def _fetch_gstin_odoo_partner_autocomplete_details(self, gstin):
        if 'res.partner' not in request.env:
            return {}

        try:
            enriched = request.env['res.partner'].sudo().enrich_by_gst(
                gstin,
                timeout=10,
            )
        except Exception:
            enriched = {}

        if not enriched or enriched.get('error'):
            try:
                india = request.env.ref('base.in', raise_if_not_found=False)
                matches = request.env['res.partner'].sudo().autocomplete_by_vat(
                    gstin,
                    india.id if india else False,
                    timeout=10,
                )
            except Exception:
                matches = []

            enriched = matches[0] if matches else {}

        return self._normalize_odoo_partner_autocomplete_payload(enriched)

    def _normalize_odoo_partner_autocomplete_payload(self, data):
        if not isinstance(data, dict) or data.get('error'):
            return {}

        state = data.get('state_id') or {}
        country = data.get('country_id') or {}

        return {
            'name': data.get('name') or '',
            'legal_name': data.get('name') or '',
            'street': data.get('street') or '',
            'street2': data.get('street2') or '',
            'city': data.get('city') or '',
            'zip': data.get('zip') or '',
            'state_id': state.get('id') if isinstance(state, dict) else False,
            'state_name': state.get('display_name') if isinstance(state, dict) else '',
            'country_id': country.get('id') if isinstance(country, dict) else False,
            'country_name': country.get('display_name') if isinstance(country, dict) else '',
            'phone': data.get('phone') or '',
            'mobile': data.get('mobile') or '',
            'email': data.get('email') or '',
            'website': data.get('website') or '',
            'l10n_in_gst_treatment': data.get('l10n_in_gst_treatment') or '',
            'gst_status': data.get('gst_status') or data.get('status') or '',
            'gst_registration_date': data.get('gst_registration_date') or '',
            'gst_taxpayer_type': data.get('gst_taxpayer_type') or '',
            'gst_constitution': data.get('gst_constitution') or '',
        }

    def _get_country_state_from_gst_details(self, details):
        country = request.env['res.country'].sudo().browse(
            details.get('country_id') or []
        ).exists()
        state = request.env['res.country.state'].sudo().browse(
            details.get('state_id') or []
        ).exists()

        if not country:
            country = self._find_country_by_name(details.get('country_name'))
        if not state:
            state = self._find_state_by_name(
                details.get('state_name'),
                country,
            )

        return country, state

    def _find_country_by_name(self, country_name):
        if not country_name:
            return request.env['res.country'].sudo()

        return request.env['res.country'].sudo().search([
            ('name', '=ilike', country_name),
        ], limit=1)

    def _find_state_by_name(self, state_name, country=False):
        if not state_name:
            return request.env['res.country.state'].sudo()

        state_name = state_name.replace('(IN)', '').strip()
        domain = ['|', ('name', '=ilike', state_name), ('l10n_in_tin', '=', state_name)]

        if country:
            domain.append(('country_id', '=', country.id))

        return request.env['res.country.state'].sudo().search(
            domain,
            limit=1,
        )

    def _fetch_gstin_provider_details(self, gstin):
        params = request.env['ir.config_parameter'].sudo()
        lookup_url = params.get_param('vendor_registration.gst_lookup_url')

        if not lookup_url:
            return {}

        url = lookup_url.format(gstin=urllib.parse.quote(gstin))
        headers = {'Accept': 'application/json'}
        token = params.get_param('vendor_registration.gst_lookup_token')

        if token:
            headers['Authorization'] = token

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            return {}

        return self._normalize_gstin_payload(payload)

    def _normalize_gstin_payload(self, payload):
        data = payload

        for key in ('data', 'result', 'response'):
            if isinstance(data, dict) and isinstance(data.get(key), dict):
                data = data[key]

        if isinstance(data, dict) and isinstance(data.get('Data'), dict):
            data = data['Data']

        if not isinstance(data, dict):
            return {}

        principal_address = data.get('pradr') or data.get('principalPlace') or {}
        address_data = {}
        address = ''

        if isinstance(principal_address, dict):
            address = principal_address.get('adr') or principal_address.get('address') or ''
            address_data = principal_address.get('addr') or {}

        if isinstance(address_data, dict) and not address:
            address_parts = [
                address_data.get('bno'),
                address_data.get('flno'),
                address_data.get('bnm'),
                address_data.get('st'),
                address_data.get('loc'),
            ]
            address = ', '.join(part for part in address_parts if part)

        if not address:
            address_parts = [
                data.get('AddrBno'),
                data.get('AddrFlno'),
                data.get('AddrBnm'),
                data.get('AddrSt'),
                data.get('AddrLoc'),
            ]
            address = ', '.join(part for part in address_parts if part)

        constitution = data.get('ctb') or data.get('Constitution') or ''
        company_type = ''
        constitution_lower = constitution.lower()
        if 'proprietor' in constitution_lower:
            company_type = 'individual'
        elif 'partnership' in constitution_lower:
            company_type = 'partnership'
        elif 'limited liability' in constitution_lower or 'llp' in constitution_lower:
            company_type = 'llp'
        elif 'private' in constitution_lower or 'public' in constitution_lower or 'company' in constitution_lower:
            company_type = 'private_ltd'

        return {
            'name': (
                data.get('tradeNam')
                or data.get('TradeName')
                or data.get('trade_name')
                or data.get('lgnm')
                or data.get('LegalName')
                or data.get('legal_name')
                or ''
            ),
            'legal_name': (
                data.get('lgnm')
                or data.get('LegalName')
                or data.get('legal_name')
                or ''
            ),
            'street': address or '',
            'city': (
                address_data.get('loc')
                or address_data.get('city')
                or data.get('AddrLoc')
                or data.get('city')
                or ''
            ),
            'zip': str(
                address_data.get('pncd')
                or data.get('AddrPncd')
                or data.get('pincode')
                or ''
            ),
            'state_name': address_data.get('stcd') or data.get('state') or '',
            'gst_status': data.get('sts') or data.get('Status') or data.get('status') or '',
            'gst_registration_date': data.get('rgdt') or data.get('DtReg') or '',
            'gst_taxpayer_type': data.get('dty') or data.get('TaxpayerType') or '',
            'gst_constitution': constitution,
            'company_type': company_type,
            'l10n_in_gst_treatment': data.get('l10n_in_gst_treatment') or '',
        }

    @http.route(
        '/vendor-registration/submit',
        type='http', auth='public', website=True, methods=['POST'],
    )
    def vendor_registration_submit(self, **kw):
        if not self._is_module_enabled():
            return self._module_disabled_response()

        form = request.httprequest.form

        name = (form.get('name') or '').strip()
        contact_name = (form.get('contact_name') or '').strip()
        email = (form.get('email') or '').strip()
        phone = (form.get('phone') or '').strip()
        mobile = (form.get('mobile') or '').strip()
        website_url = (form.get('website') or '').strip()
        company_type = (form.get('company_type') or 'individual').strip()
        gst_number = (form.get('gst_number') or '').strip().upper()
        gst_treatment = (
            form.get('l10n_in_gst_treatment')
            or 'unregistered'
        ).strip()
        pan_number = (form.get('pan_number') or '').strip().upper()
        cin_number = (form.get('cin_number') or '').strip().upper()
        msme_number = (form.get('msme_number') or '').strip()
        street = (form.get('street') or '').strip()
        street2 = (form.get('street2') or '').strip()
        city = (form.get('city') or '').strip()
        zip_code = (form.get('zip') or '').strip()
        bank_name = (form.get('bank_name') or '').strip()
        bank_account_number = (form.get('bank_account_number') or '').strip()
        bank_ifsc = (form.get('bank_ifsc') or '').strip().upper()
        bank_branch = (form.get('bank_branch') or '').strip()
        years_in_business = form.get('years_in_business') or 0
        annual_turnover = form.get('annual_turnover') or False
        notes = (form.get('notes') or '').strip()
        gst_autofill_details = {}

        if gst_number:
            gst_autofill_details = self._fetch_gstin_odoo_partner_autocomplete_details(
                gst_number
            )

            if gst_autofill_details:
                fetched_name = (
                    gst_autofill_details.get('name')
                    or gst_autofill_details.get('legal_name')
                    or ''
                )
                name = fetched_name or name
                contact_name = contact_name or gst_autofill_details.get('legal_name') or name
                email = email or gst_autofill_details.get('email') or ''
                phone = phone or gst_autofill_details.get('phone') or ''
                mobile = mobile or gst_autofill_details.get('mobile') or ''
                website_url = website_url or gst_autofill_details.get('website') or ''
                street = street or gst_autofill_details.get('street') or ''
                street2 = street2 or gst_autofill_details.get('street2') or ''
                city = city or gst_autofill_details.get('city') or ''
                zip_code = zip_code or gst_autofill_details.get('zip') or ''
                company_type = (
                    company_type
                    if company_type != 'individual'
                    else gst_autofill_details.get('company_type') or company_type
                )
                gst_treatment = (
                    gst_autofill_details.get('l10n_in_gst_treatment')
                    or gst_treatment
                )

        form_values = {
            'name': name, 'contact_name': contact_name, 'email': email,
            'phone': phone, 'mobile': mobile, 'website': website_url,
            'company_type': company_type, 'gst_number': gst_number,
            'l10n_in_gst_treatment': gst_treatment,
            'pan_number': pan_number, 'cin_number': cin_number,
            'msme_number': msme_number, 'street': street, 'street2': street2,
            'city': city, 'zip': zip_code, 'bank_name': bank_name,
            'bank_account_number': bank_account_number, 'bank_ifsc': bank_ifsc,
            'bank_branch': bank_branch, 'years_in_business': years_in_business,
            'annual_turnover': annual_turnover, 'notes': notes,
        }

        # Validation
        if not name:
            return request.render('vendor_registration.vendor_registration_form',
                self._prepare_registration_values(_('Company / Vendor Name is required.'), form_values))
        if not email:
            return request.render('vendor_registration.vendor_registration_form',
                self._prepare_registration_values(_('Email is required.'), form_values))
        if not phone:
            return request.render('vendor_registration.vendor_registration_form',
                self._prepare_registration_values(_('Phone is required.'), form_values))
        if not street:
            return request.render('vendor_registration.vendor_registration_form',
                self._prepare_registration_values(_('Street / Address Line 1 is required.'), form_values))
        if not street2:
            return request.render('vendor_registration.vendor_registration_form',
                self._prepare_registration_values(_('Address Line 2 is required.'), form_values))
        if not city:
            return request.render('vendor_registration.vendor_registration_form',
                self._prepare_registration_values(_('City is required.'), form_values))
        if not zip_code:
            return request.render('vendor_registration.vendor_registration_form',
                self._prepare_registration_values(_('PIN Code is required.'), form_values))
        if gst_number and len(gst_number) != 15:
            return request.render('vendor_registration.vendor_registration_form',
                self._prepare_registration_values(_('GST Number must be exactly 15 characters.'), form_values))

        # Duplicate check
        existing = request.env['vendor.registration'].sudo().search(
            [('email', '=', email), ('state', '!=', 'rejected')], limit=1)
        if existing:
            return request.render('vendor_registration.vendor_registration_form',
                self._prepare_registration_values(
                    _('A registration with this email already exists.'), form_values))
        if gst_number:
            existing = request.env['vendor.registration'].sudo().search(
                [('gst_number', '=', gst_number), ('state', 'in', ('draft', 'approved'))],
                limit=1,
            )
            if existing:
                return request.render('vendor_registration.vendor_registration_form',
                    self._prepare_registration_values(
                        _('A registration with this GST number is already pending or approved.'),
                        form_values))

        # Country / State
        country_id = False
        state_id = False
        try:
            raw_country = form.get('country_id')
            if raw_country:
                country_id = int(raw_country)
            raw_state = form.get('state_id')
            if raw_state:
                state_id = int(raw_state)
        except ValueError:
            pass
        if gst_number and (not country_id or not state_id):
            gst_details = self._get_gstin_derived_details(gst_number)
            gst_details.update(gst_autofill_details)
            country, state = self._get_country_state_from_gst_details(
                gst_details
            )
            country_id = country_id or country.id
            state_id = state_id or state.id
        form_values.update({
            'country_id': country_id,
            'state_id': state_id,
        })
        if not country_id:
            return request.render('vendor_registration.vendor_registration_form',
                self._prepare_registration_values(_('Country is required.'), form_values))
        if not state_id:
            return request.render('vendor_registration.vendor_registration_form',
                self._prepare_registration_values(_('State is required.'), form_values))

        vals = {
            'name': name, 'contact_name': contact_name, 'email': email,
            'phone': phone, 'mobile': mobile, 'website': website_url,
            'company_type': company_type, 'gst_number': gst_number or False,
            'l10n_in_gst_treatment': gst_treatment or False,
            'pan_number': pan_number or False, 'cin_number': cin_number or False,
            'msme_number': msme_number or False, 'street': street, 'street2': street2,
            'city': city, 'zip': zip_code, 'state_id': state_id, 'country_id': country_id,
            'bank_name': bank_name, 'bank_account_number': bank_account_number,
            'bank_ifsc': bank_ifsc, 'bank_branch': bank_branch,
            'annual_turnover': annual_turnover or False, 'notes': notes,
        }
        try:
            vals['years_in_business'] = int(years_in_business)
        except (ValueError, TypeError):
            vals['years_in_business'] = 0

        reg = request.env['vendor.registration'].sudo().create(vals)
        reg.message_post(
            body=_(
                'New vendor registration submitted from website portal.\n'
                'Vendor: %s\n'
                'Contact: %s\n'
                'Email: %s\n'
                'Phone: %s\n'
                'GST: %s'
            ) % (
                reg.name,
                reg.contact_name or '-',
                reg.email,
                reg.phone or '-',
                reg.gst_number or '-',
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        # Send acknowledgement email
        template = request.env.ref(
            'vendor_registration.mail_template_vendor_received_v2',
            raise_if_not_found=False,
        )
        if template:
            try:
                template.sudo().send_mail(reg.id, force_send=True)
            except Exception as exc:
                reg.sudo().message_post(
                    body=_('Acknowledgement email could not be sent: %s') % exc,
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )

        return request.render(
            'vendor_registration.vendor_registration_form',
            self._prepare_registration_values(success=True),
        )

    # ── Portal: Register Products / Services ─────────────────────────────────

    @http.route(
        '/my/vendor-products',
        type='http', auth='public', website=True,
    )
    def vendor_products_portal(self, **kw):
        if not self._is_module_enabled():
            return self._module_disabled_response()

        if request.env.user._is_public():
            return redirect('/web/login?redirect=/my/vendor-products')

        partner = request.env.user.partner_id
        reg = request.env['vendor.registration'].sudo().search(
            [('partner_id', '=', partner.id), ('state', '=', 'approved')], limit=1)

        if not reg:
            return request.render('vendor_registration.vendor_not_approved', {})

        submitted = request.env['vendor.product.request'].sudo().search(
            [('vendor_registration_id', '=', reg.id)], order='create_date desc')

        return request.render('vendor_registration.vendor_product_form', {
            'page_name': 'vendor_products',
            'registration': reg,
            'submitted_products': submitted,
            'allow_bulk_upload': reg.partner_id.allow_bulk_upload,
            'error': kw.get('error'),
            'success': kw.get('success'),
        })

    @http.route(
        '/my/vendor-products/search-products',
        type='jsonrpc',
        auth='user',
        website=True,
        methods=['POST'],
    )
    def vendor_products_search_products(self, query=None):
        if not self._is_module_enabled():
            return []
        query = (query or '').strip()

        if len(query) < 2:
            return []

        products = request.env['product.template'].sudo().search([
            ('name', 'ilike', query),
            ('active', '=', True),
            ('purchase_ok', '=', True),
        ], limit=8)

        return [{
            'id': product.id,
            'name': product.display_name,
            'type': product.type,
            'uom': product.uom_po_id.name or product.uom_id.name or '',
            'price': product.standard_price or 0.0,
            'l10n_in_hsn_code': product.l10n_in_hsn_code or '',
        } for product in products]

    @http.route(
        '/my/vendor-products/search-hsn',
        type='jsonrpc',
        auth='user',
        website=True,
        methods=['POST'],
    )
    def vendor_products_search_hsn(self, query=None, product_type='goods'):
        if not self._is_module_enabled():
            return []

        import json
        import urllib.parse
        import urllib.request

        query = (query or '').strip()

        if len(query) < 3:
            return []

        only_digits = query.isdigit()
        params = (
            [{'selectedType': 'byCode', 'category': 'null'}]
            if only_digits
            else [{
                'selectedType': 'byDesc',
                'category': 'S' if product_type == 'service' else 'P',
            }]
        )
        suggestions = []

        for param in params:
            query_string = urllib.parse.urlencode({
                'inputText': query,
                **param,
            })
            url = (
                'https://services.gst.gov.in/commonservices/hsn/search/qsearch?'
                + query_string
            )

            try:
                req = urllib.request.Request(
                    url,
                    headers={'User-Agent': 'Mozilla/5.0'},
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    payload = json.loads(response.read().decode('utf-8'))
            except Exception:
                continue

            for item in payload.get('data') or []:
                code = item.get('c')
                if code and len(code) > 3:
                    suggestions.append({
                        'code': code,
                        'description': item.get('n') or '',
                    })

        return suggestions[:10]

    @http.route(
        '/my/vendor-products/submit',
        type='http', auth='public', website=True, methods=['POST'],
    )
    def vendor_products_submit(self, **kw):
        if not self._is_module_enabled():
            return self._module_disabled_response()

        if request.env.user._is_public():
            return redirect('/web/login?redirect=/my/vendor-products')

        partner = request.env.user.partner_id
        reg = request.env['vendor.registration'].sudo().search(
            [('partner_id', '=', partner.id), ('state', '=', 'approved')], limit=1)

        if not reg:
            return redirect('/my/vendor-products')

        form = request.httprequest.form
        product_name = (form.get('name') or '').strip()
        existing_product_tmpl_id = form.get('existing_product_tmpl_id')
        product_type = form.get('product_type') or 'goods'
        description = (form.get('description') or '').strip()
        uom = (form.get('uom') or '').strip()
        hsn_code = (
            form.get('l10n_in_hsn_code')
            or form.get('hsn_code')
            or ''
        ).strip()
        brand = (form.get('brand') or '').strip()
        model_number = (form.get('model_number') or '').strip()
        certifications = (form.get('certifications') or '').strip()

        try:
            price = float(form.get('price') or 0)
        except ValueError:
            price = 0.0
        try:
            min_order_qty = float(form.get('min_order_qty') or 1)
        except ValueError:
            min_order_qty = 1.0
        try:
            lead_time = int(form.get('lead_time') or 0)
        except ValueError:
            lead_time = 0
        try:
            tax_percent = float(form.get('tax_percent') or 0)
        except ValueError:
            tax_percent = 0.0

        if not product_name:
            return redirect('/my/vendor-products?error=Product+name+is+required.')

        existing_template = request.env['product.template'].sudo()
        if existing_product_tmpl_id:
            try:
                existing_template = request.env['product.template'].sudo().browse(
                    int(existing_product_tmpl_id)
                ).exists()
            except ValueError:
                existing_template = request.env['product.template'].sudo()
        if not existing_template:
            existing_template = self._find_existing_product_template(product_name)
        hsn_code = hsn_code or existing_template.l10n_in_hsn_code or ''
        request_vals = {
            'name': product_name,
            'vendor_registration_id': reg.id,
            'product_type': product_type,
            'description': description,
            'uom': uom,
            'price': price,
            'min_order_qty': min_order_qty,
            'lead_time': lead_time,
            'l10n_in_hsn_code': hsn_code,
            'tax_percent': tax_percent,
            'brand': brand,
            'model_number': model_number,
            'certifications': certifications,
        }
        if existing_template:
            request_vals['existing_product_id'] = existing_template.id
        product_request = request.env['vendor.product.request'].sudo().create(request_vals)

        # If product already exists, directly add vendor as supplier and mark merged.
        if existing_template:
            product_request.sudo().action_approve()
            reg.message_post(
                body=_(
                    'Vendor product mapped directly to existing product: %s. '
                    'Vendor added in product vendor lines.'
                ) % existing_template.display_name,
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )
            return redirect('/my/vendor-products?success=1')

        product_request.message_post(
            body=_(
                'Product/service submitted from vendor portal by %s.\n'
                'Item: %s\n'
                'Type: %s\n'
                'Price: %s'
            ) % (
                request.env.user.name,
                product_request.name,
                product_request._get_product_type_label(),
                product_request.price,
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )
        reg.message_post(
            body=_(
                'Vendor submitted a new product/service request for approval: %s.'
            ) % product_request.name,
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        return redirect('/my/vendor-products?success=1')

    # -------------------------------------------------------------------------
    # Download Excel Template
    # -------------------------------------------------------------------------

    @http.route(
        '/my/vendor-products/template',
        type='http',
        auth='user',
        website=True
    )
    def download_vendor_product_template(self, **kw):
        if not self._is_module_enabled():
            return self._module_disabled_response()

        import io
        import pandas as pd

        template_type = (kw.get('type') or 'all').lower()
        columns = [
            'product_name',
            'type',
            'description',
            'uom',
            'hsn_code',
            'brand',
            'model_number',
            'certifications',
            'price',
            'tax_percent',
            'min_order_qty',
            'lead_time',
        ]

        if template_type == 'service':
            filename = 'vendor_service_template.xlsx'
            df = pd.DataFrame([{
                'product_name': '',
                'type': 'service',
                'description': '',
                'uom': '',
                'hsn_code': '',
                'brand': '',
                'model_number': '',
                'certifications': '',
                'price': 0,
                'tax_percent': 18,
                'min_order_qty': 1,
                'lead_time': 0,
            }], columns=columns)
        elif template_type == 'goods':
            filename = 'vendor_goods_template.xlsx'
            df = pd.DataFrame([{
                'product_name': '',
                'type': 'goods',
                'description': '',
                'uom': '',
                'hsn_code': '',
                'brand': '',
                'model_number': '',
                'certifications': '',
                'price': 0,
                'tax_percent': 18,
                'min_order_qty': 1,
                'lead_time': 0,
            }], columns=columns)
        else:
            filename = 'vendor_product_template.xlsx'
            df = pd.DataFrame(columns=columns)

        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(
                writer,
                index=False,
                sheet_name='Products'
            )

        output.seek(0)

        return request.make_response(
            output.read(),
            headers=[
                (
                    'Content-Type',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                ),
                (
                    'Content-Disposition',
                    'attachment; filename=%s' % filename
                ),
            ]
        )

    # -------------------------------------------------------------------------
    # Bulk Upload Products
    # -------------------------------------------------------------------------

    @http.route(
        '/my/vendor-products/bulk-upload',
        type='http',
        auth='user',
        website=True,
        methods=['POST']
    )
    def vendor_products_bulk_upload(self, **post):
        if not self._is_module_enabled():
            return self._module_disabled_response()

        import pandas as pd
        import io

        user = request.env.user
        partner = user.partner_id

        if not partner.allow_bulk_upload:
            return redirect('/my/vendor-products?error=Bulk+upload+is+not+enabled+for+your+contact')

        reg = request.env['vendor.registration'].sudo().search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'approved')
        ], limit=1)

        if not reg:
            return redirect('/my/vendor-products?error=Vendor+not+approved')

        uploaded_file = request.httprequest.files.get('product_file')

        if not uploaded_file:
            return redirect('/my/vendor-products?error=No+file+uploaded')

        try:

            filename = uploaded_file.filename.lower()

            file_content = uploaded_file.read()

            # CSV
            if filename.endswith('.csv'):

                df = pd.read_csv(
                    io.BytesIO(file_content)
                )

            # Excel
            else:

                df = pd.read_excel(
                    io.BytesIO(file_content),
                    engine='openpyxl'
                )

        except Exception as e:

            print("FILE READ ERROR:", str(e))

            return redirect(
                '/my/vendor-products?error=Invalid+Excel+file'
            )

        ProductRequest = request.env['vendor.product.request'].sudo()

        created_count = 0

        # -------------------------------------------------------------
        # Helper Functions
        # -------------------------------------------------------------

        def clean_string(value):

            if pd.isna(value):
                return ''

            if isinstance(value, float) and value.is_integer():
                return str(int(value))

            value = str(value).strip()

            if value.endswith('.0') and value[:-2].isdigit():
                return value[:-2]

            return value

        def clean_hsn_code(row):

            return clean_string(
                row.get('l10n_in_hsn_code')
                if 'l10n_in_hsn_code' in row
                else row.get('hsn_code')
            )

        def clean_float(value, default=0):

            try:

                if pd.isna(value):
                    return default

                return float(value)

            except:
                return default

        def clean_int(value, default=0):

            try:

                if pd.isna(value):
                    return default

                return int(float(value))

            except:
                return default

        # -------------------------------------------------------------
        # Process Rows
        # -------------------------------------------------------------

        for _, row in df.iterrows():

            try:

                product_name = clean_string(
                    row.get('product_name')
                )

                # Skip empty rows
                if not product_name:
                    continue

                product_type = clean_string(
                    row.get('type')
                ).lower()

                if product_type not in ['goods', 'service']:
                    product_type = 'goods'

                # -----------------------------------------------------
                # Auto Detect Existing Product
                # -----------------------------------------------------

                existing_template = self._find_existing_product_template(
                    product_name
                )
                hsn_code = (
                    clean_hsn_code(row)
                    or existing_template.l10n_in_hsn_code
                    or ''
                )

                vals = {

                    'name': product_name,

                    'vendor_registration_id': reg.id,

                    'product_type': product_type,

                    'description': clean_string(
                        row.get('description')
                    ),

                    'uom': clean_string(
                        row.get('uom')
                    ),

                    'l10n_in_hsn_code': hsn_code,

                    'brand': clean_string(
                        row.get('brand')
                    ),

                    'model_number': clean_string(
                        row.get('model_number')
                    ),

                    'certifications': clean_string(
                        row.get('certifications')
                    ),

                    'price': clean_float(
                        row.get('price'),
                        0
                    ),

                    'tax_percent': clean_float(
                        row.get('tax_percent'),
                        18
                    ),

                    'min_order_qty': clean_float(
                        row.get('min_order_qty'),
                        1
                    ),

                    'lead_time': clean_int(
                        row.get('lead_time'),
                        0
                    ),
                }

                # -----------------------------------------------------
                # Auto Map Existing Product
                # -----------------------------------------------------

                if existing_template:
                    vals['existing_product_id'] = existing_template.id

                product_request = ProductRequest.create(vals)

                # -----------------------------------------------------
                # Auto Approve Existing Product Mapping
                # -----------------------------------------------------

                if existing_template:
                    product_request.action_approve()

                created_count += 1

            except Exception as row_error:

                print("ROW ERROR:", str(row_error))

                continue

        return redirect(
            f'/my/vendor-products?success={created_count}+products+uploaded+successfully'
        )
