from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ITAssetRequisitionInherit(models.Model):
    _inherit = 'it.asset.requisition'

    employee_id = fields.Many2one('hr.employee', string='Employee')
    manager_id = fields.Many2one('hr.employee', string='Manager')

    approval_request_id = fields.Many2one('approval.request', string='Approval')

    rfq_count = fields.Integer(compute="_compute_counts")
    approval_count = fields.Integer(compute="_compute_counts")

    def _compute_counts(self):
        for rec in self:
            rec.rfq_count = 1 if rec.purchase_id else 0
            rec.approval_count = 1 if rec.approval_request_id else 0

    # =========================
    # AUTOFILL EMPLOYEE FIELDS
    # =========================
    @api.onchange('employee_id')
    def _onchange_employee(self):
        for rec in self:
            emp = rec.employee_id
            if emp:
                name_parts = (emp.name or '').split(' ', 1)
                rec.emp_first_name = name_parts[0] if name_parts else ''
                rec.emp_last_name = name_parts[1] if len(name_parts) > 1 else ''
                rec.emp_designation = emp.job_title or emp.job_id.name or ''
                rec.emp_department = emp.department_id.name or ''
                rec.emp_office_site = emp.work_location_id.name or ''
                rec.emp_code = emp.emp_code or ''
                rec.emp_location = emp.work_location_id.name or ''

                if emp.parent_id:
                    rec.manager_id = emp.parent_id

    # =========================
    # AUTOFILL MANAGER FIELDS
    # =========================
    @api.onchange('manager_id')
    def _onchange_manager(self):
        for rec in self:
            mgr = rec.manager_id
            if mgr:
                name_parts = (mgr.name or '').split(' ', 1)
                rec.manager_first_name = name_parts[0] if name_parts else ''
                rec.manager_last_name = name_parts[1] if len(name_parts) > 1 else ''
                rec.manager_location = mgr.work_location_id.name or ''

    # =========================
    # CREATE RFQ (Purchase Managers Only — enforced in view)
    # =========================
    def create_rfq(self):
        for rec in self:
            if rec.purchase_id:
                raise ValidationError("Only one RFQ allowed per request.")

            lines = []
            products = [
                rec.hardware_product_id,
                rec.sim_product_id,
                rec.printer_product_id
            ]

            for product in products:
                if product:
                    lines.append((0, 0, {
                        'product_id': product.id,
                        'name': product.display_name,
                        'product_qty': 1,
                        'price_unit': product.standard_price or 0.0,
                        'product_uom_id': product.uom_id.id,
                        'date_planned': fields.Datetime.now(),
                    }))

            if not lines:
                raise ValidationError("Select at least one product.")

            partner = self.env['res.partner'].search(
                [('supplier_rank', '>', 0)], limit=1
            ) or self.env.user.partner_id

            po = self.env['purchase.order'].create({
                'partner_id': partner.id,
                'origin': rec.name,
                'order_line': lines,
                'it_asset_requisition_id': rec.id,
            })

            rec.purchase_id = po.id

    # =========================
    # OPEN RFQ
    # =========================
    def action_open_rfq(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'RFQ',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', '=', self.purchase_id.id)],
            'res_id': self.purchase_id.id,
        }

    # =========================
    # CATEGORY AUTO CREATE
    # =========================
    def _get_category(self):
        category = self.env['approval.category'].search(
            [('name', '=', 'Asset Requisition')], limit=1
        )

        if not category:
            admin = self.env.ref('base.user_admin')
            category = self.env['approval.category'].create({
                'name': 'Asset Requisition',
                'approver_ids': [(0, 0, {
                    'user_id': admin.id,
                    'required': True
                })]
            })

        return category

    # =========================
    # REQUEST APPROVAL
    # =========================
    def action_request_approval(self):
        for rec in self:
            if not rec.purchase_id:
                raise ValidationError("Please create an RFQ first before requesting approval.")

            if rec.approval_request_id:
                raise ValidationError("Approval already exists.")

            category = rec._get_category()

            approval = self.env['approval.request'].create({
                'category_id': category.id,
                'request_owner_id': self.env.user.id,
                'name': f"{rec.name} - IT Asset Purchase Approval",
                'reason': f"Auto-generated from {rec.name}",
                'it_requisition_id': rec.id,
            })

            approval.action_confirm()

            rec.approval_request_id = approval.id
            rec.state = 'submitted'

    # =========================
    # OPEN APPROVAL
    # =========================
    def action_open_approval(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Approval',
            'res_model': 'approval.request',
            'view_mode': 'list,form',
            'domain': [('id', '=', self.approval_request_id.id)],
            'res_id': self.approval_request_id.id,
        }


# ==========================================================
# APPROVAL REQUEST INHERIT — sync state on approve
# ==========================================================
class ApprovalRequestInherit(models.Model):
    _inherit = 'approval.request'

    # Link back to requisition for easy navigation
    it_requisition_id = fields.Many2one('it.asset.requisition', string='IT Asset Requisition', readonly=True)

    # Mirror fields from requisition for display in Approval screen
    req_employee_id = fields.Many2one(related='it_requisition_id.employee_id', string='Employee', readonly=True)
    req_department = fields.Char(related='it_requisition_id.emp_department', string='Department', readonly=True)
    req_designation = fields.Char(related='it_requisition_id.emp_designation', string='Designation', readonly=True)
    req_manager_id = fields.Many2one(related='it_requisition_id.manager_id', string='Manager', readonly=True)
    req_hardware = fields.Many2one(related='it_requisition_id.hardware_product_id', string='Computer Hardware', readonly=True)
    req_sim = fields.Many2one(related='it_requisition_id.sim_product_id', string='SIM Card', readonly=True)
    req_printer = fields.Many2one(related='it_requisition_id.printer_product_id', string='Printer', readonly=True)
    req_software_checkbox = fields.Boolean(related='it_requisition_id.software_checkbox', string='Software', readonly=True)
    req_software_specify = fields.Char(related='it_requisition_id.software_specify', string='Software Name', readonly=True)
    req_pda_checkbox = fields.Boolean(related='it_requisition_id.pda_checkbox', string='PDA', readonly=True)
    req_pda_count = fields.Integer(related='it_requisition_id.pda_count', string='PDA Count', readonly=True)
    req_others_text = fields.Text(related='it_requisition_id.others_text', string='Others', readonly=True)
    req_justification_type = fields.Selection(related='it_requisition_id.justification_type', string='Justification Type', readonly=True)
    req_justification_text = fields.Text(related='it_requisition_id.justification_text', string='Justification', readonly=True)
    req_ist_remark = fields.Text(related='it_requisition_id.ist_remark', string='IS&T Remark', readonly=True)
    req_manager_remarks = fields.Text(related='it_requisition_id.manager_remarks', string='Manager Remarks', readonly=True)

    def action_approve(self, approver=None):
        res = super().action_approve(approver=approver)

        for rec in self:
            if rec.request_status == 'approved':
                requisitions = self.env['it.asset.requisition'].search([
                    ('approval_request_id', '=', rec.id)
                ])
                for req in requisitions:
                    req.state = 'approved'
                    req.is_approved = True
                    po = req.purchase_id
                    if po and po.state in ['draft', 'sent']:
                        po.button_confirm()

        return res


class HrEmployeeInherit(models.Model):
    _inherit = 'hr.employee'

    emp_code = fields.Char(string="Employee Code")


class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    asset_category = fields.Selection([
        ('hardware', 'Computer Hardware'),
        ('printer', 'Printer'),
        ('sim', 'SIM Card'),
    ], string="Asset Category")
