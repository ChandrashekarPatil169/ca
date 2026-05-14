# -*- coding: utf-8 -*-
{
    'name': 'Website Product Requisition',
    'version': '19.0.1.2.0',
    'category': 'Website/CRM',
    'summary': 'Collect product requisitions from the website and create CRM leads with order lines.',
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': [
        'website',
        'website_sale',
        'portal',
        'crm',
        'sale_crm',          # needed for action_new_quotation on crm.lead
        'sale_management',
        'dgz_crm_orderlines',
        'zb_product_approve',
    ],
    'data': [
        'data/ir_config_parameter_data.xml',
        'data/product_requisition_data.xml',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/product_requisition_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'product_requisition/static/src/css/product_requisition_chatbot.css',
            'product_requisition/static/src/js/product_requisition.js',
        ],
    },
    'installable': True,
    'application': False,
}
