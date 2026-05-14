# -*- coding: utf-8 -*-
import base64
import csv
import io
import logging
import re
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CSV_HEADERS = [
    'customer_name',
    'customer_ref',
    'state',
    'branch',
    'zone',
    'city',
    'address',
    'email',
    'phone',
    'role',
    'product_code',
    'product_desc',
    'serial_id',
    'warranty_code',
    'warranty_desc',
    'warranty_start_date',
    'warranty_end_date',
    'dealer_code',
    'dealer_name',
    'product_category_code',
    'product_category_desc',
]


class DealerSampleImport(models.AbstractModel):
    _name = 'dealer.sample.import'
    _description = 'Dealer Tracking Sample Import'

    @api.model
    def action_import_csv(self, csv_text):
        created = {'customers': 0, 'dealers': 0, 'lots': 0}
        reader = csv.DictReader(io.StringIO(csv_text))
        missing_headers = [header for header in CSV_HEADERS if header not in (reader.fieldnames or [])]
        if missing_headers:
            raise UserError(_("Missing CSV columns: %s") % ', '.join(missing_headers))

        for row in reader:
            customer = self._upsert_customer(row, created)
            dealer = self._upsert_dealer(row, created)
            product = self._upsert_product(row)
            if product and row.get('serial_id'):
                self._upsert_lot(row, customer, dealer, product, created)

        _logger.info("Dealer data import completed: %s", created)
        return created

    def _get_or_create(self, model_name, domain, vals):
        record = self.env[model_name].sudo().search(domain, limit=1)
        if record:
            record.write(vals)
            return record, False
        return self.env[model_name].sudo().create(vals), True

    def _master(self, model_name, name):
        name = (name or '').strip()
        if not name:
            return False
        return self._get_or_create(model_name, [('name', '=', name)], {'name': name})[0]

    def _country_india(self):
        return self.env.ref('base.in', raise_if_not_found=False)

    def _state(self, state_name):
        state_name = (state_name or '').strip()
        country = self._country_india()
        if not state_name or not country:
            return False
        return self.env['res.country.state'].sudo().search([
            ('country_id', '=', country.id),
            ('name', '=ilike', state_name),
        ], limit=1)

    def _parse_address(self, address):
        parts = [(part or '').strip() for part in (address or '').split('/')]
        street = parts[0] if parts else ''
        zip_match = re.search(r'\b\d{6}\b', address or '')
        return street, zip_match.group(0) if zip_match else ''

    def _upsert_customer(self, row, created):
        branch = self._master('dealer.branch', row.get('branch'))
        zone = self._master('dealer.zone', row.get('zone'))
        country = self._country_india()
        state = self._state(row.get('state'))
        street, zip_code = self._parse_address(row.get('address'))
        ref = (row.get('customer_ref') or '').strip()

        vals = {
            'name': row.get('customer_name'),
            'ref': ref or False,
            'street': street or False,
            'city': row.get('city') or False,
            'zip': zip_code or False,
            'email': row.get('email') or False,
            'phone': row.get('phone') or False,
            'branch_id': branch.id if branch else False,
            'zone_id': zone.id if zone else False,
            'country_id': country.id if country else False,
            'state_id': state.id if state else False,
        }
        domain = [('ref', '=', ref)] if ref else [('name', '=', row.get('customer_name'))]
        customer, is_created = self._get_or_create('res.partner', domain, vals)
        if is_created:
            created['customers'] += 1

        role = (row.get('role') or '').strip()
        if role:
            tag = self._master('res.partner.category', role)
            customer.category_id = [(4, tag.id)]
        return customer

    def _upsert_dealer(self, row, created):
        dealer_name = (row.get('dealer_name') or '').strip()
        dealer_code = (row.get('dealer_code') or '').strip()
        if not dealer_name:
            return False
        vals = {
            'name': dealer_name,
            'is_dealer': True,
            'dealer_code': dealer_code or False,
        }
        domain = [('dealer_code', '=', dealer_code)] if dealer_code else [('name', '=', dealer_name), ('is_dealer', '=', True)]
        dealer, is_created = self._get_or_create('res.partner', domain, vals)
        if is_created:
            created['dealers'] += 1
        return dealer

    def _upsert_product(self, row):
        code = (row.get('product_code') or '').strip()
        name = (row.get('product_desc') or code).strip()
        if not code and not name:
            return False

        category = False
        category_code = (row.get('product_category_code') or '').strip()
        category_name = (row.get('product_category_desc') or '').strip()
        if category_name or category_code:
            category_domain = [('dealer_category_code', '=', category_code)] if category_code else [('name', '=', category_name)]
            category = self._get_or_create(
                'product.category',
                category_domain,
                {
                    'name': category_name or category_code,
                    'dealer_category_code': category_code or False,
                    'dealer_category_description': category_name or False,
                },
            )[0]

        vals = {
            'name': name,
            'default_code': code or False,
            'categ_id': category.id if category else False,
        }
        domain = [('default_code', '=', code)] if code else [('name', '=', name)]
        return self._get_or_create('product.product', domain, vals)[0]

    def _upsert_lot(self, row, customer, dealer, product, created):
        warranty_type = self._upsert_warranty_type(row)
        vals = {
            'name': row.get('serial_id'),
            'product_id': product.id,
            'customer_id': customer.id if customer else False,
            'dealer_id': dealer.id if dealer else False,
            'warranty_type_id': warranty_type.id if warranty_type else False,
            'warranty_description': row.get('warranty_desc') or False,
            'warranty_start_date': row.get('warranty_start_date') or False,
            'warranty_end_date': row.get('warranty_end_date') or False,
            'warranty_duration': self._warranty_duration(row),
        }
        lot = self.env['stock.lot'].sudo().search([
            ('name', '=', row.get('serial_id')),
            ('product_id', '=', product.id),
        ], limit=1)
        if lot:
            lot.write(vals)
        else:
            self.env['stock.lot'].sudo().create(vals)
            created['lots'] += 1

    def _upsert_warranty_type(self, row):
        code = (row.get('warranty_code') or '').strip()
        description = (row.get('warranty_desc') or '').strip()
        if not code and not description:
            return False
        return self._get_or_create(
            'dealer.warranty.type',
            [('code', '=', code)] if code else [('name', '=', description)],
            {
                'name': code or description,
                'code': code or False,
                'description': description or False,
            },
        )[0]

    def _warranty_duration(self, row):
        start = row.get('warranty_start_date')
        end = row.get('warranty_end_date')
        if not start or not end:
            return False
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
        months = relativedelta(end_date + relativedelta(days=1), start_date)
        total_months = months.years * 12 + months.months
        if total_months >= 35:
            return '36'
        if total_months >= 23:
            return '24'
        if total_months >= 17:
            return '18'
        if total_months >= 11:
            return '12'
        return '6'


class DealerDataImportWizard(models.TransientModel):
    _name = 'dealer.data.import.wizard'
    _description = 'Import Dealer Tracking Data'

    csv_file = fields.Binary(string="CSV File", required=True)
    filename = fields.Char(string="Filename")

    def action_import(self):
        self.ensure_one()
        if self.filename and not self.filename.lower().endswith('.csv'):
            raise UserError(_("Please upload a CSV file."))

        raw = base64.b64decode(self.csv_file or b'')
        try:
            csv_text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            csv_text = raw.decode('latin1')

        result = self.env['dealer.sample.import'].action_import_csv(csv_text)
        message = _(
            "Import completed. Customers: %(customers)s, Dealers: %(dealers)s, Serials: %(lots)s"
        ) % result
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Dealer Data Import"),
                'message': message,
                'type': 'success',
                'sticky': False,
            },
        }
