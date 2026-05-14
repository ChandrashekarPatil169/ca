from odoo import models, fields, api
from datetime import date


class ResPartner(models.Model):
    _inherit = 'res.partner'

    serial_count = fields.Integer(
        string="Serial Count",
        compute="_compute_serial_count"
    )

    def _compute_serial_count(self):
        for partner in self:
            lots = self.env['stock.lot'].search([
                '|',
                ('customer_id', '=', partner.id),
                ('dealer_id', '=', partner.id)
            ])
            partner.serial_count = len(lots)

    def action_view_serials(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Serial Numbers',
            'res_model': 'stock.lot',
            'view_mode': 'list,form',
            'domain': [
                '|',
                ('customer_id', '=', self.id),
                ('dealer_id', '=', self.id)
            ],
            'context': {
                'default_customer_id': self.id
            }
        }


class StockLot(models.Model):
    _inherit = 'stock.lot'

    # ------------------------
    # WARRANTY FIELDS
    # ------------------------

    warranty_start_date = fields.Date(
        string="Warranty Start Date"
    )

    warranty_duration = fields.Selection(
        [
            ('6', '6 Months'),
            ('12', '12 Months'),
            ('18', '18 Months'),
            ('24', '24 Months'),
            ('36', '36 Months'),
        ],
        string="Warranty Duration"
    )

    warranty_end_date = fields.Date(
        string="Warranty End Date"
    )


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    # -------------------------
    # SERIAL NUMBER
    # -------------------------
    lot_id = fields.Many2one(
        'stock.lot',
        string="Product Serial Number",
        domain="""
        [
            '|',
            ('customer_id', '=', partner_id),
            ('dealer_id', '=', partner_id)
        ]
        """
    )

    # -------------------------
    # WARRANTY STATUS (ALWAYS LIVE)
    # -------------------------
    warranty_status = fields.Selection(
        [
            ('in_warranty', 'In Warranty'),
            ('out_warranty', 'Out of Warranty')
        ],
        string="Warranty Status",
        compute="_compute_warranty_status"
    )

    # -------------------------
    # FORCE LIVE FETCH (NO CACHE)
    # -------------------------
    def _get_latest_warranty_date(self):
        self.ensure_one()

        if not self.lot_id:
            return False

        # Always fetch fresh value from DB
        lot = self.env['stock.lot'].browse(self.lot_id.id).sudo()
        return lot.warranty_end_date

    @api.depends('lot_id')
    def _compute_warranty_status(self):
        today = date.today()

        for rec in self:
            warranty_end = False

            if rec.lot_id:
                warranty_end = rec._get_latest_warranty_date()

            if warranty_end:
                if today <= warranty_end:
                    rec.warranty_status = 'in_warranty'
                else:
                    rec.warranty_status = 'out_warranty'
            else:
                rec.warranty_status = False
