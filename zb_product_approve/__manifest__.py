# -*- encoding: utf-8 -*-
##############################################################################
#
#    Copyright (c) 2024 ZestyBeanz Technologies
#    (http://wwww.zbeanztech.com)
#    contact@zbeanztech.com
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': 'Product Approval',
    'summary': "This module helps to manage the product approval process with Draft & Approve Stages. Sales Order / Purchase Order can be confirmed & Invoice can be Posted only when the Products are in Approved Stage.",
    'version': '19.0.0.0',
    'category': "Extra Tools",
    'website': "http://www.zbeanztech.com/",
    'description': """
         This module helps to manage the product approval process with Draft & Approve Stages. Sales Order / Purchase Order can be confirmed & Invoice can be Posted only when the Products are in Approved Stage.
    """,
    'author': 'ZestyBeanz Technologies',
    'maintainer': 'ZestyBeanz Technologies',
    'support': 'support@zbeanztech.com',
    'license': 'LGPL-3',
    'icon': "/zb_product_approve/static/description/icon.png",
    'images': ['static/description/banners/banner.png',],
    'license': 'LGPL-3',
    'currency': 'USD',
    'price': 0.0,
    'depends': ['sale_management','purchase','stock'],
    'data': [
        'security/security.xml',
        'views/product_view.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
}
