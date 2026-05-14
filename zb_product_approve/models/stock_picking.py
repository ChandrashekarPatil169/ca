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
from odoo import models, fields,api,_
from odoo.exceptions import UserError

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _is_product_requisition_module_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'product_requisition.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')

    def button_validate(self):
        if not self._is_product_requisition_module_enabled():
            return super(StockPicking, self).button_validate()

        for rec in self:
            unapproved_products = ", ".join(line.product_id.name for line in rec.move_line_ids if line.product_id and line.product_id.state not in ('approved', 'mapped'))
            if unapproved_products:
                raise UserError("These Products are Not Approved or Mapped ({}) Please Approve or Map all Products Before Validating the Picking.".format(unapproved_products))
        return super(StockPicking, self).button_validate()
