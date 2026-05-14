# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class DealerTrackingController(http.Controller):

    # -------------------------------------------------------
    # OVERRIDE the helpdesk team submit page
    # -------------------------------------------------------
    @http.route(
        ['/helpdesk/<string:team_id>',
         '/helpdesk/<string:team_id>/<string:ticket_id>'],
        type='http', auth='user', website=True, sitemap=False
    )
    def website_helpdesk_submit(self, team_id=None, ticket_id=None, **kwargs):
        team = request.env['helpdesk.team'].sudo().search(
            [('use_website_helpdesk_form', '=', True)], limit=1
        )

        user = request.env.user
        partner = user.partner_id

        dealers = request.env['res.partner'].sudo().search([('is_dealer', '=', True)])

        # Serials linked to the logged-in user's partner
        lots = request.env['stock.lot'].sudo().search([
            ('customer_id', '=', partner.id)
        ])

        return request.render('dealer_tracking.website_helpdesk_form_custom', {
            'team':         team,
            'dealers':      dealers,
            'lots':         lots,
            'partner':      partner,
        })

    # -------------------------------------------------------
    # Handle custom form POST submission
    # -------------------------------------------------------
    @http.route('/dealer_tracking/submit_ticket', type='http',
                auth='user', website=True, methods=['POST'], csrf=True)
    def submit_ticket(self, **post):
        team = request.env['helpdesk.team'].sudo().search(
            [('use_website_helpdesk_form', '=', True)], limit=1
        )

        user    = request.env.user
        partner = user.partner_id

        vals = {
            'name':         post.get('subject', 'Website Ticket'),
            'description':  post.get('description', ''),
            'partner_id':   partner.id,           # always the logged-in user
            'partner_name': partner.name,
            'partner_email':partner.email or '',
            'partner_phone':post.get('partner_phone', ''),
            'team_id':      team.id if team else False,
        }

        dealer_id = post.get('dealer_id')
        if dealer_id:
            vals['dealer_id'] = int(dealer_id)

        lot_id = post.get('lot_id')
        if lot_id:
            vals['lot_id'] = int(lot_id)

        request.env['helpdesk.ticket'].sudo().create(vals)
        return request.redirect('/')

    # -------------------------------------------------------
    # JSON RPC: lots filtered by logged-in customer + dealer
    # -------------------------------------------------------
    @http.route('/get_lots', type='jsonrpc', auth='user', website=True)
    def get_lots(self, dealer_id=None):
        partner = request.env.user.partner_id

        # Domain mirrors backend lot_domain:
        # always scoped to the logged-in customer's serials
        domain = [('customer_id', '=', partner.id)]

        if dealer_id:
            domain.append(('dealer_id', '=', int(dealer_id)))

        lots = request.env['stock.lot'].sudo().search(domain)
        return [{'id': l.id, 'name': l.name} for l in lots]

    # -------------------------------------------------------
    # JSON RPC: lot details (auto-fill dealer)
    # -------------------------------------------------------
    @http.route('/get_lot_details', type='jsonrpc', auth='user', website=True)
    def get_lot_details(self, lot_id):
        lot = request.env['stock.lot'].sudo().browse(int(lot_id))
        return {
            'dealer_id': lot.dealer_id.id if hasattr(lot, 'dealer_id') and lot.dealer_id else False,
        }

