from odoo import models, fields, api


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    # -------------------------------
    # DEALER FIELD
    # -------------------------------
    dealer_id = fields.Many2one(
        'res.partner',
        string="Dealer",
        domain=[('is_dealer', '=', True)]
    )

    # -------------------------------
    # DYNAMIC DOMAIN FIELD (IMPORTANT)
    # -------------------------------
    lot_domain = fields.Binary(
        compute="_compute_lot_domain"
    )

    # -------------------------------
    # COMPUTE DOMAIN (MAIN FIX)
    # -------------------------------
    @api.depends('partner_id', 'dealer_id')
    def _compute_lot_domain(self):
        for rec in self:

            # Case 1: Nothing selected → show all
            if not rec.partner_id and not rec.dealer_id:
                domain = []

            # Case 2: Only customer
            elif rec.partner_id and not rec.dealer_id:
                domain = [
                    ('customer_id', '=', rec.partner_id.id)
                ]

            # Case 3: Only dealer ✅ YOUR CASE
            elif rec.dealer_id and not rec.partner_id:
                domain = [
                    ('dealer_id', '=', rec.dealer_id.id)
                ]

            # Case 4: Both
            else:
                domain = [
                    ('customer_id', '=', rec.partner_id.id),
                    ('dealer_id', '=', rec.dealer_id.id)
                ]

            rec.lot_domain = domain

    # -------------------------------
    # RESET SERIAL ON CHANGE
    # -------------------------------
    # @api.onchange('partner_id', 'dealer_id')
    # def _onchange_partner_or_dealer(self):
    #     self.lot_id = False

    # -------------------------------
    # AUTO-FILL CUSTOMER + DEALER
    # -------------------------------

    @api.onchange('lot_id')
    def _onchange_lot_id_autofill(self):
        if self.lot_id:
            self.partner_id = self.lot_id.customer_id
            self.dealer_id = self.lot_id.dealer_id

            # ✅ Email works normally
            self.email_cc = self.partner_id.email or False

            # 🔥 FORCE phone update (THIS IS THE FIX)
            self.partner_phone = self.partner_id.phone or False
            self.is_partner_phone_update = False