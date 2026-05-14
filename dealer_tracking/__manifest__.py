# -*- coding: utf-8 -*-
{
    'name': 'Dealer Tracking with Serial Link',
    'version': '1.0',
    'summary': 'Track dealer, customer and location from serial numbers',

    'author': 'Your Name',
    'license': 'LGPL-3',

    'depends': [
        'sale',
        'helpdesk',
        'website_helpdesk',
        'stock',
        'contacts',
    ],

    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/helpdesk_ticket_view.xml',
    ],

    # ✅ IMPORTANT (JS LOADING FIX)
    'assets': {
        'web.assets_frontend': [
            'dealer_tracking/static/src/js/helpdesk_form.js',
        ],
    },

    'installable': True,
    'application': False,
}
