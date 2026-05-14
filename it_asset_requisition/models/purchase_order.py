
from odoo import models, fields
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    it_asset_requisition_id = fields.Many2one('it.asset.requisition', string='IT Asset Requisition', readonly=True)
    
    # Related fields for visibility in PO form
    emp_first_name = fields.Char(related='it_asset_requisition_id.emp_first_name', string='Emp First Name')
    emp_last_name = fields.Char(related='it_asset_requisition_id.emp_last_name', string='Emp Last Name')
    emp_department = fields.Char(related='it_asset_requisition_id.emp_department', string='Emp Department')
    emp_location = fields.Char(related='it_asset_requisition_id.emp_location', string='Emp Location')
    
    manager_first_name = fields.Char(related='it_asset_requisition_id.manager_first_name', string='Manager First Name')
    manager_last_name = fields.Char(related='it_asset_requisition_id.manager_last_name', string='Manager Last Name')
    manager_remarks = fields.Text(related='it_asset_requisition_id.manager_remarks', string='Manager Remarks')
    
    justification_type = fields.Selection(related='it_asset_requisition_id.justification_type', string='Justification Type')
    justification_text = fields.Text(related='it_asset_requisition_id.justification_text', string='Justification Details')
    
    others_text = fields.Text(related='it_asset_requisition_id.others_text', string='Additional Requirements')
    needs_approval = fields.Boolean(default=False)
    def button_confirm(self):
        for order in self:
            requisition = order.it_asset_requisition_id
            if requisition:
                approval = requisition.approval_request_id
                if not approval or approval.request_status != 'approved':
                    raise UserError(
                        "This RFQ cannot be confirmed manually. "
                        "The approval request for requisition '%s' has not been approved yet."
                        % requisition.name
                    )
        return super().button_confirm()
