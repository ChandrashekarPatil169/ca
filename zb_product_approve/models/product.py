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

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ProductTemplate(models.Model):
    _inherit = "product.template"
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('mapped', 'Mapped'),
    ], string="Approve Status", default="draft", tracking=True)
    mapped_product_tmpl_id = fields.Many2one(
        'product.template',
        string='Map It',
        domain="[('id', '!=', id), ('active', '=', True)]",
        tracking=True,
    )

    def _is_product_requisition_module_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'product_requisition.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')
    
    def action_verify(self):
        if not self._is_product_requisition_module_enabled():
            return True

        for rec in self:
            if rec.state == 'mapped':
                raise UserError(_("Once a product is mapped you cannot approve it."))
            rec.state = 'approved'

    def write(self, vals):
        if self._is_product_requisition_module_enabled():
            if 'mapped_product_tmpl_id' in vals:
                for rec in self:
                    if rec.state == 'approved' and vals.get('mapped_product_tmpl_id'):
                        raise UserError(_("Cannot map it once approved."))
            if vals.get('state') == 'approved':
                for rec in self:
                    if rec.state == 'mapped':
                        raise UserError(_("Once a product is mapped you cannot approve it."))
        return super().write(vals)

    def action_map_product(self):
        if not self._is_product_requisition_module_enabled():
            return True

        for rec in self:
            if rec.state == 'approved':
                raise UserError(_("Cannot map it once approved."))
            if not rec.mapped_product_tmpl_id:
                raise UserError(_("Please select a product to map."))
            rec.state = 'mapped'
                
    def action_draft(self):
        if not self._is_product_requisition_module_enabled():
            return True

        for rec in self:
            rec.write({'state': 'draft', 'mapped_product_tmpl_id': False})
    
class Product(models.Model):
    _inherit = "product.product"

    mapped_product_id = fields.Many2one(
        'product.product',
        string='Mapped Product',
        related='product_tmpl_id.mapped_product_tmpl_id.product_variant_id',
        store=False,
        readonly=True,
    )

    def _is_product_requisition_module_enabled(self):
        value = self.env['ir.config_parameter'].sudo().get_param(
            'product_requisition.module_enabled',
            'True',
        )
        return str(value).lower() not in ('false', '0', 'no', 'off')
             
    def action_verify(self):
        if not self._is_product_requisition_module_enabled():
            return True

        for rec in self:
            if rec.state == 'mapped':
                raise UserError(_("Once a product is mapped you cannot approve it."))
            rec.state = 'approved'

    def action_map_product(self):
        if not self._is_product_requisition_module_enabled():
            return True

        for rec in self:
            rec.product_tmpl_id.action_map_product()
                
    def action_draft(self):
        if not self._is_product_requisition_module_enabled():
            return True

        for rec in self:
            rec.product_tmpl_id.action_draft()
