from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class UserAccessForm(models.Model):
    _name = 'it.user.access.form'
    _description = 'User Access Form'
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default='New')
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('task_created', 'Task Created'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status', tracking=True)

    request_date = fields.Date(string='Request Date', default=fields.Date.context_today)
    employee_id = fields.Many2one('hr.employee', string='Employee Name', required=True)
    first_name = fields.Char(string='First Name')
    last_name = fields.Char(string='Last Name')
    department_location = fields.Char(string='Department / Location')
    extension_no = fields.Char(string='Extension No')
    location_code = fields.Char(string='Location Code')
    location = fields.Char(string='Location')
    designation = fields.Char(string='Designation')
    manager_id = fields.Many2one('hr.employee', string='Department Head / Manager')

    domain_account = fields.Boolean(string='Domain Account')
    ehrms_access = fields.Boolean(string='eHRMS')
    eiis_access = fields.Boolean(string='eIIS')
    elms_access = fields.Boolean(string='eLMS')
    md_sl_access = fields.Boolean(string='MD-SL')
    hyperion_access = fields.Boolean(string='Hyperion')
    sonar_access = fields.Boolean(string='Sonar')
    email_id_required = fields.Boolean(string='Email-ID')
    email_id = fields.Char(string='E-Mail ID')

    shared_drive_access = fields.Boolean(string='Shared Drive Access')
    drive_p = fields.Boolean(string='P Drive')
    drive_o = fields.Boolean(string='O Drive')
    drive_m = fields.Boolean(string='M Drive')
    drive_r = fields.Boolean(string='R Drive')
    drive_h = fields.Boolean(string='H Drive')
    drive_g = fields.Boolean(string='G Drive')
    drive_i = fields.Boolean(string='I Drive')

    internet_access = fields.Boolean(string='Internet Access')
    lan_access = fields.Boolean(string='LAN Access Required')
    wi_data_access = fields.Boolean(string='WI-DATA Access')
    guest_wifi_only = fields.Boolean(string='Guest Wi-Fi Only')
    user_id_text = fields.Char(string='User ID')
    computer_name = fields.Char(string='Computer Name')
    access_level = fields.Char(string='Access Level')
    policy_confirmed = fields.Boolean(string='Policy Confirmed')
    employee_signature = fields.Char(string='Employee Signature')
    department_head_name = fields.Char(string='Department Head / Manager Name')
    department_head_signature = fields.Char(string='Department Head / Manager Signature')
    general_manager_name = fields.Char(string='General Manager Name')
    general_manager_signature = fields.Char(string='General Manager Signature')
    ist_created_by = fields.Char(string='Created By')
    ist_signature = fields.Char(string='IS & T Signature')
    notes = fields.Text(string='Notes')
    description = fields.Html(string='Description')

    project_id = fields.Many2one('project.project', string='Project', default=lambda self: self._get_user_access_project())
    task_id = fields.Many2one('project.task', string='Task', readonly=True)
    approval_request_id = fields.Many2one('approval.request', string='Approval Request', readonly=True)
    approval_count = fields.Integer(compute='_compute_counts')
    task_count = fields.Integer(compute='_compute_counts')

    @api.depends('approval_request_id', 'task_id')
    def _compute_counts(self):
        for rec in self:
            rec.approval_count = 1 if rec.approval_request_id else 0
            rec.task_count = 1 if rec.task_id else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('it.user.access.form') or 'New'
            if vals.get('employee_id'):
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                vals.update({key: value for key, value in self._prepare_employee_values(employee).items() if not vals.get(key)})
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('employee_id'):
            employee = self.env['hr.employee'].browse(vals['employee_id'])
            vals = dict(vals)
            vals.update(self._prepare_employee_values(employee))
        return super().write(vals)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        for rec in self:
            rec._set_employee_values()

    def _set_employee_values(self):
        self.ensure_one()
        if not self.employee_id:
            return
        self.update(self._prepare_employee_values(self.employee_id))

    @api.model
    def _prepare_employee_values(self, emp):
        name_parts = (emp.name or '').split(' ', 1)
        return {
            'first_name': name_parts[0] if name_parts else '',
            'last_name': name_parts[1] if len(name_parts) > 1 else '',
            'department_location': emp.department_id.name or emp.work_location_id.name or '',
            'location': emp.work_location_id.name or '',
            'designation': emp.job_title or emp.job_id.name or '',
            'extension_no': emp.work_phone or '',
            'email_id': emp.work_email or '',
            'manager_id': emp.parent_id.id,
            'department_head_name': emp.parent_id.name or '',
        }

    def _get_role_users(self):
        Groups = self.env['res.groups'].sudo()
        dept_group = self.env.ref('it_asset_requisition.group_user_access_department_manager')
        gm_group = self.env.ref('it_asset_requisition.group_user_access_general_manager')

        employees = self.env['hr.employee'].sudo().search([
            ('active', '=', True),
            ('work_email', '!=', False),
        ], order='id', limit=2)
        users = self.env['res.users'].sudo()
        for employee in employees:
            users |= self._get_or_create_employee_user(employee)

        if len(users) < 2:
            users |= self.env['res.users'].sudo().search([
                ('share', '=', False),
                ('id', 'not in', users.ids),
            ], order='id', limit=2 - len(users))

        admin = self.env.ref('base.user_admin').sudo()
        dept_user = users[:1] or admin
        gm_user = (users - dept_user)[:1] or admin

        Groups.browse(dept_group.id).write({'user_ids': [(6, 0, [dept_user.id])]})
        Groups.browse(gm_group.id).write({'user_ids': [(6, 0, [gm_user.id])]})
        return dept_user, gm_user

    @api.model
    def _get_or_create_employee_user(self, employee):
        if employee.user_id:
            return employee.user_id.sudo()

        login = employee.work_email or employee.name
        user = self.env['res.users'].sudo().search([('login', '=', login)], limit=1)
        if not user:
            user = self.env['res.users'].sudo().with_context(no_reset_password=True).create({
                'name': employee.name,
                'login': login,
                'email': employee.work_email or False,
                'company_id': employee.company_id.id or self.env.company.id,
                'company_ids': [(4, employee.company_id.id or self.env.company.id)],
                'group_ids': [(4, self.env.ref('base.group_user').id)],
            })
        employee.sudo().user_id = user.id
        return user

    def _get_user_access_category(self):
        category = self.env['approval.category'].sudo().search([
            ('name', '=', 'User Access Requisition'),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        dept_user, gm_user = self._get_role_users()
        approver_commands = []
        seen_users = set()
        for sequence, user in ((10, dept_user), (20, gm_user)):
            if user and user.id not in seen_users:
                seen_users.add(user.id)
                approver_commands.append((0, 0, {
                    'user_id': user.id,
                    'required': True,
                    'sequence': sequence,
                }))
        if not category:
            category = self.env['approval.category'].sudo().create({
                'name': 'User Access Requisition',
                'approval_minimum': 2 if len(approver_commands) >= 2 else len(approver_commands) or 1,
                'approver_sequence': True,
                'approver_ids': approver_commands,
            })
        else:
            category.write({
                'approval_minimum': 2 if len(approver_commands) >= 2 else len(approver_commands) or 1,
                'approver_sequence': True,
                'approver_ids': [(5, 0, 0)] + approver_commands,
            })
        return category

    @api.model
    def _setup_user_access_approval_flow(self):
        self._get_user_access_project()
        return self._get_user_access_category()

    @api.model
    def _get_user_access_project(self):
        project = self.env['project.project'].sudo().search([('name', '=', 'User Access Project')], limit=1)
        if not project:
            project = self.env['project.project'].sudo().create({'name': 'User Access Project'})
        return project.id

    def action_request_approval(self):
        for rec in self:
            if rec.approval_request_id:
                raise ValidationError(_('Approval already requested.'))
            if not rec.employee_id:
                raise ValidationError(_('Please select an employee before requesting approval.'))
            if not rec.project_id:
                rec.project_id = rec._get_user_access_project()
            category = rec._get_user_access_category()
            reason = (_('<p>User Access Form: %s</p><p>Employee: %s</p>') % (
                rec.name,
                rec.employee_id.name,
            )) + (rec.description or '')
            approval = self.env['approval.request'].sudo().create({
                'category_id': category.id,
                'request_owner_id': self.env.user.id,
                'name': _('%s - User Access Approval') % rec.name,
                'reason': reason,
                'user_access_form_id': rec.id,
            })
            approval.action_confirm()
            rec.write({'approval_request_id': approval.id, 'state': 'submitted'})

    def action_admin_approve(self):
        for rec in self:
            if not rec.approval_request_id:
                raise ValidationError(_('Please request approval first.'))
            rec.approval_request_id.sudo()._action_force_approval()
            rec._create_user_access_task()

    def _create_user_access_task(self):
        for rec in self:
            if rec.task_id:
                continue
            if not rec.project_id:
                rec.project_id = rec._get_user_access_project()
            task = self.env['project.task'].sudo().create({
                'name': _('%s - User Access for %s') % (rec.name, rec.employee_id.name or ''),
                'project_id': rec.project_id.id,
                'user_access_form_id': rec.id,
                'description': rec._get_task_description(),
            })
            rec.write({'task_id': task.id, 'state': 'task_created'})

    def _get_task_description(self):
        self.ensure_one()
        enabled = [
            label for field_name, label in [
                ('domain_account', 'Domain Account'),
                ('ehrms_access', 'eHRMS'),
                ('eiis_access', 'eIIS'),
                ('elms_access', 'eLMS'),
                ('md_sl_access', 'MD-SL'),
                ('hyperion_access', 'Hyperion'),
                ('sonar_access', 'Sonar'),
                ('email_id_required', 'Email-ID'),
                ('shared_drive_access', 'Shared Drive Access'),
                ('internet_access', 'Internet Access'),
                ('lan_access', 'LAN Access'),
                ('wi_data_access', 'WI-DATA Access'),
                ('guest_wifi_only', 'Guest Wi-Fi Only'),
            ] if self[field_name]
        ]
        summary = '<br/>'.join([
            _('Employee: %s') % (self.employee_id.name or ''),
            _('Department / Location: %s') % (self.department_location or ''),
            _('User ID: %s') % (self.user_id_text or ''),
            _('Computer Name: %s') % (self.computer_name or ''),
            _('Access Level: %s') % (self.access_level or ''),
            _('Access Required For: %s') % (', '.join(enabled) or '-'),
        ])
        return summary + (('<br/><br/>' + self.description) if self.description else '')

    def action_print_user_access_form(self):
        self.ensure_one()
        return self.env.ref('it_asset_requisition.action_report_user_access_form').report_action(self)

    def action_open_approval(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Approval Request',
            'res_model': 'approval.request',
            'view_mode': 'form',
            'res_id': self.approval_request_id.id,
        }

    def action_open_task(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'User Access Task',
            'res_model': 'project.task',
            'view_mode': 'form',
            'res_id': self.task_id.id,
        }


class ApprovalRequestUserAccessInherit(models.Model):
    _inherit = 'approval.request'

    user_access_form_id = fields.Many2one('it.user.access.form', string='User Access Form', readonly=True)
    user_access_form_count = fields.Integer(compute='_compute_user_access_form_count')
    user_access_employee_id = fields.Many2one(related='user_access_form_id.employee_id', string='Employee', readonly=True)
    user_access_project_id = fields.Many2one(related='user_access_form_id.project_id', string='Project', readonly=True)
    user_access_task_id = fields.Many2one(related='user_access_form_id.task_id', string='Task', readonly=True)
    user_access_description = fields.Html(related='user_access_form_id.description', string='User Access Description', readonly=True)

    def _compute_user_access_form_count(self):
        for rec in self:
            rec.user_access_form_count = 1 if rec.user_access_form_id else 0

    def action_open_user_access_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'User Access Form',
            'res_model': 'it.user.access.form',
            'view_mode': 'form',
            'res_id': self.user_access_form_id.id,
        }

    def action_approve(self, approver=None):
        res = super().action_approve(approver=approver)
        for rec in self.filtered(lambda approval: approval.user_access_form_id and approval.request_status == 'approved'):
            rec.user_access_form_id._create_user_access_task()
        return res


class HrEmployeeUserAccessInherit(models.Model):
    _inherit = 'hr.employee'

    user_access_form_ids = fields.One2many('it.user.access.form', 'employee_id', string='User Access Forms')
    user_access_form_count = fields.Integer(compute='_compute_user_access_form_count')

    def _compute_user_access_form_count(self):
        for employee in self:
            employee.user_access_form_count = len(employee.user_access_form_ids)

    def action_open_user_access_forms(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'User Access Forms',
            'res_model': 'it.user.access.form',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }


class ProjectTaskUserAccessInherit(models.Model):
    _inherit = 'project.task'

    user_access_form_id = fields.Many2one('it.user.access.form', string='User Access Form', readonly=True)
    user_access_form_count = fields.Integer(compute='_compute_user_access_form_count')

    def _compute_user_access_form_count(self):
        for task in self:
            task.user_access_form_count = 1 if task.user_access_form_id else 0

    def action_open_user_access_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'User Access Form',
            'res_model': 'it.user.access.form',
            'view_mode': 'form',
            'res_id': self.user_access_form_id.id,
        }
