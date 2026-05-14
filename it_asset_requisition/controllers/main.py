
from odoo import http
from odoo.http import request

class ITAssetController(http.Controller):

    @http.route('/it-asset/request', type='http', auth='user', website=True)
    def asset_form(self):
        # We search by category name or provide a way to configure this if needed
        # For now, searching by name as per implementation plan
        cats = request.env['product.category'].sudo().search([
            ('name', 'in', ['IT Hardware', 'IT SIM', 'IT Printer'])
        ])
        cat_map = {cat.name: cat.id for cat in cats}
        
        Product = request.env['product.product'].sudo()
        import datetime
        return request.render('it_asset_requisition.asset_form', {
            'hardware_products': Product.search([('categ_id', '=', cat_map.get('IT Hardware'))]) if cat_map.get('IT Hardware') else [],
            'sim_products': Product.search([('categ_id', '=', cat_map.get('IT SIM'))]) if cat_map.get('IT SIM') else [],
            'printer_products': Product.search([('categ_id', '=', cat_map.get('IT Printer'))]) if cat_map.get('IT Printer') else [],
            'datetime': datetime,
            'success': request.params.get('success'),
        })

    @http.route('/it-asset/submit', type='http', auth='user', website=True, csrf=True)
    def asset_submit(self, **post):
        vals = {
            'emp_first_name': post.get('emp_first_name'),
            'emp_last_name': post.get('emp_last_name'),
            'emp_designation': post.get('emp_designation'),
            'emp_department': post.get('emp_department'),
            'emp_office_site': post.get('emp_office_site'),
            'emp_code': post.get('emp_code'),
            'emp_location': post.get('emp_location'),
            'request_date': post.get('request_date') or False,
            
            'manager_first_name': post.get('manager_first_name'),
            'manager_last_name': post.get('manager_last_name'),
            'manager_location': post.get('manager_location'),
            'manager_date': post.get('manager_date') or False,
            'manager_remarks': post.get('manager_remarks'),
            'email_approval': post.get('email_approval') == 'on',

            'hardware_product_id': int(post.get('hardware_product_id')) if post.get('hardware_product_id') else False,
            'sim_product_id': int(post.get('sim_product_id')) if post.get('sim_product_id') else False,
            'printer_product_id': int(post.get('printer_product_id')) if post.get('printer_product_id') else False,
            
            'software_checkbox': post.get('software_checkbox') == 'on',
            'software_specify': post.get('software_specify'),
            'pda_checkbox': post.get('pda_checkbox') == 'on',
            'pda_count': int(post.get('pda_count')) if post.get('pda_count') else 0,
            'others_text': post.get('others_text'),
            'justification_type': post.get('justification_type'),
            'justification_text': post.get('justification_text'),
        }
        rec = request.env['it.asset.requisition'].sudo().create(vals)
        rec.create_rfq()
        return request.redirect('/it-asset/request?success=1')
