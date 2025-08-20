# -*- coding:utf-8 -*-

import babel
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta
from pytz import timezone
from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError


class HrPayslip(models.Model):
    _name = 'hr.payslip'
    _description = 'Pay Slip'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    struct_id = fields.Many2one('hr.payroll.structure', string='Structure',
        readonly=True, states={'draft': [('readonly', False)]},
        help='Defines the rules that have to be applied to this payslip, accordingly '
             'to the contract chosen. If you let empty the field contract, this field isn\'t '
             'mandatory anymore and thus the rules applied will be all the rules set on the '
             'structure of all contracts of the employee valid for the chosen period')
    name = fields.Char(string='Payslip Name', readonly=True,
        states={'draft': [('readonly', False)]})
    number = fields.Char(string='Reference', readonly=True, copy=False,
        states={'draft': [('readonly', False)]})
    employee_id = fields.Many2one(
        'hr.employee', string='Employee',
        required=True, readonly=True,
        states={'draft': [('readonly', False)]})
    date_from = fields.Date(
        string='Date From', readonly=True, required=True,
        default=lambda self: fields.Date.to_string(date.today().replace(day=1)),
        states={'draft': [('readonly', False)]})
    date_to = fields.Date(
        string='Date To', readonly=True, required=True,
        default=lambda self: fields.Date.to_string(
            (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()
        ), states={'draft': [('readonly', False)]})
    # this is chaos: 4 states are defined, 3 are used ('verify' isn't) and 5 exist ('confirm' seems to have existed)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('verify', 'Waiting'),
        ('done', 'Done'),
        ('cancel', 'Rejected'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft',
        help="""* When the payslip is created the status is \'Draft\'
                \n* If the payslip is under verification, the status is \'Waiting\'.
                \n* If the payslip is confirmed then status is set to \'Done\'.
                \n* When user cancel payslip the status is \'Rejected\'.""")
    line_ids = fields.One2many(
        'hr.payslip.line', 'slip_id',
        string='Payslip Lines', readonly=True,
        states={'draft': [('readonly', False)]}
    )
    company_id = fields.Many2one(
        'res.company', string='Company', readonly=True, copy=False,
        default=lambda self: self.env.company,
        states={'draft': [('readonly', False)]})
    worked_days_line_ids = fields.One2many('hr.payslip.worked_days', 'payslip_id',
        string='Payslip Worked Days', copy=True, readonly=True,
        states={'draft': [('readonly', False)]})
    input_line_ids = fields.One2many('hr.payslip.input', 'payslip_id', string='Payslip Inputs',
        readonly=True, copy=True, states={'draft': [('readonly', False)]})
    paid = fields.Boolean(string='Made Payment Order ? ', readonly=True, copy=False,
        states={'draft': [('readonly', False)]})
    note = fields.Text(string='Internal Note', readonly=True, states={'draft': [('readonly', False)]})
    contract_id = fields.Many2one('hr.contract', string='Contract', readonly=True,
        states={'draft': [('readonly', False)]})
    details_by_salary_rule_category = fields.One2many('hr.payslip.line',
        compute='_compute_details_by_salary_rule_category', string='Details by Salary Rule Category')
    credit_note = fields.Boolean(string='Credit Note', readonly=True,
        states={'draft': [('readonly', False)]},
        help="Indicates this payslip has a refund of another")
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Payslip Batches', readonly=True,
        copy=False, states={'draft': [('readonly', False)]})
    payslip_count = fields.Integer(compute='_compute_payslip_count', string="Payslip Computation Details")

    def _compute_details_by_salary_rule_category(self):
        for payslip in self:
            payslip.details_by_salary_rule_category = payslip.mapped('line_ids').filtered(lambda line: line.category_id)

    def _compute_payslip_count(self):
        for payslip in self:
            payslip.payslip_count = len(payslip.line_ids)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        if any(self.filtered(lambda payslip: payslip.date_from > payslip.date_to)):
            raise ValidationError(_("Payslip 'Date From' must be earlier 'Date To'."))

    def action_payslip_draft(self):
        return self.write({'state': 'draft'})

    def action_payslip_done(self):
        self.compute_sheet()
        return self.write({'state': 'done'})

    def action_payslip_cancel(self):
        # if self.filtered(lambda slip: slip.state == 'done'):
        #     raise UserError(_("Cannot cancel a payslip that is done."))
        return self.write({'state': 'cancel'})

    def refund_sheet(self):
        """
        Generate a refund payslip (credit note) for each payslip in the recordset.

        This method performs the following steps for each payslip:
          1. Creates a copy of the payslip with `credit_note=True` and
             updates its name to indicate it is a refund.
          2. Recomputes the copied payslip using `compute_sheet()`.
          3. Marks the refund payslip as done using `action_payslip_done()`.

        After processing, it returns an `ir.actions.act_window` action
        that opens the tree and form views of the newly created refund payslips.

        Returns:
            dict: An Odoo action dictionary to display the refund payslips
                  in tree and form views.
        """
        for payslip in self:
            copied_payslip = payslip.copy({'credit_note': True, 'name': _('Refund: ') + payslip.name})
            copied_payslip.compute_sheet()
            copied_payslip.action_payslip_done()
        form_view_ref = self.env.ref('om_jm_hr_payroll.view_hr_payslip_form', False)
        tree_view_ref = self.env.ref('om_jm_hr_payroll.view_hr_payslip_tree', False)
        return {
            'name': (_("Refund Payslip")),
            'view_mode': 'tree, form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'hr.payslip',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'domain': "[('id', 'in', %s)]" % copied_payslip.ids,
            'views': [(tree_view_ref and tree_view_ref.id or False, 'tree'),
                      (form_view_ref and form_view_ref.id or False, 'form')],
            'context': {}
        }

    def action_send_email(self):
        """
            Open the email composition wizard pre-filled with the payslip email template.

            This method ensures only one payslip is selected, retrieves the predefined
            payslip email template (if available), and launches the Odoo email
            composition wizard. The wizard allows the user to send the payslip to the
            employee via email.

            Workflow:
                1. Validate a single payslip record using `ensure_one()`.
                2. Fetch the email template `jm_hr_payroll.mail_template_payslip` if defined.
                3. Retrieve the compose message wizard form view.
                4. Pass default values (model, res_id, template, mode) in context.
                5. Return an action that opens the wizard in a popup window.

            Returns:
                dict: An `ir.actions.act_window` dictionary that opens the
                `mail.compose.message` form view in a modal popup with pre-filled
                template and context for sending the payslip via email.

            Raises:
                ValueError: If the email template or the compose form view XMLID
                cannot be found, though both are handled gracefully by falling back
                to `False`.
        """
        self.ensure_one()
        ir_model_data = self.env['ir.model.data']
        try:
            template_id = self.env.ref('jm_hr_payroll.mail_template_payslip').id
        except ValueError:
            template_id = False
        try:
            compose_form_id = ir_model_data._xmlid_lookup('mail.email_compose_message_wizard_form')[2]
        except ValueError:
            compose_form_id = False
        ctx = {
            'default_model': 'hr.payslip',
            'default_res_id': self.ids[0],
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
        }
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }

    def check_done(self):
        return True

    def unlink(self):
        if any(self.filtered(lambda payslip: payslip.state not in ('draft', 'cancel'))):
            raise UserError(_('You cannot delete a payslip which is not draft or cancelled!'))
        return super(HrPayslip, self).unlink()

    # TODO move this function into hr_contract module, on hr.employee object
    @api.model
    def get_contract(self, employee, date_from, date_to):
        """
        Retrieve active contracts for an employee within a given date range.

        A contract is considered valid for the given range if:
            1. The contract ends within the range [date_from, date_to].
            2. The contract starts within the range [date_from, date_to].
            3. The contract starts before `date_from` and ends after `date_to`
               (or has no end date, meaning it's still active).

        Args:
            employee (hr.employee recordset): The employee whose contracts are checked.
            date_from (date): Start of the reference period.
            date_to (date): End of the reference period.

        Returns:
            list: IDs of `hr.contract` records that are active for the employee
            during the specified date range.

        Notes:
            - Only contracts in state = 'open' are considered.
            - Covers overlapping cases to ensure correct payroll computation.
        """
        # Clause 1: contract ends inside the given range
        clause_1 = ['&', ('date_end', '<=', date_to), ('date_end', '>=', date_from)]

        # Clause 2: contract starts inside the given range
        clause_2 = ['&', ('date_start', '<=', date_to), ('date_start', '>=', date_from)]

        # Clause 3: contract starts before date_from and ends after date_to (or is still open-ended)
        clause_3 = ['&', ('date_start', '<=', date_from), '|', ('date_end', '=', False), ('date_end', '>=', date_to)]

        # Combine all clauses with OR
        clause_final = [
                           ('employee_id', '=', employee.id),
                           ('state', '=', 'open'),
                           '|', '|'
                       ] + clause_1 + clause_2 + clause_3

        return self.env['hr.contract'].search(clause_final).ids

    def compute_sheet(self):
        """Computes the payslip for each record in the current set.
        This method performs the following steps:
            1. Generates a unique payslip number using the salary slip
             sequence (if not already set).
            2. Deletes any existing payslip lines to avoid duplication.
            3. Determines the contracts applicable for the employee
             during the payslip period:
             - Uses the contract linked to the payslip if available,
              otherwise fetches all active contracts of the employee
              within the given dates using `get_contract`.
            4. Raises a ValidationError if no valid contract is found
             for the employee in the given period.
            5. Computes and prepares payslip lines based on salary
             rules from the retrieved contracts.
            6. Updates the payslip record with the computed lines
             and assigned payslip number.

        Returns:
            bool: Always returns True upon successful computation of the payslip.
        """
        for payslip in self:
            number = payslip.number or self.env['ir.sequence'].next_by_code('salary.slip')
            # delete old payslip lines
            payslip.line_ids.unlink()
            # set the list of contract for which the rules have to be applied
            contract_ids = payslip.contract_id.ids or \
                           self.get_contract(
                               payslip.employee_id,
                               payslip.date_from,
                               payslip.date_to
                           )
            if not contract_ids:
                raise ValidationError(
                    _("No running contract found for the employee:"
                      " %s or no contract in the given period"
                      % payslip.employee_id.name))
            lines = [(0, 0, line) for line in self._get_payslip_lines(
                contract_ids, payslip.id
            )]
            payslip.write({'line_ids': lines, 'number': number})
        return True

    @api.model
    def get_worked_day_lines(self, contracts, date_from, date_to):
        """
            Compute worked day lines and leave information for the given contracts
            within a specified date range.

            This method calculates:
              - Worked days and hours based on the employee's resource calendar.
              - Leaves taken during the period, adjusting days and hours accordingly.

            Args:
                contracts (recordset): hr.contract records to process.
                                       Only contracts with a working schedule
                                       (resource_calendar_id) are considered.
                date_from (str): Start date of the computation period (YYYY-MM-DD).
                date_to (str): End date of the computation period (YYYY-MM-DD).

            Returns:
                list[dict]: A list of dictionaries containing attendance and leave
                            information. Each dictionary includes:
                                - name (str): Description of work/leave type.
                                - sequence (int): Ordering of lines.
                                - code (str): Code for worked/leave type (e.g., WORK100).
                                - number_of_days (float): Number of days worked/leave.
                                - number_of_hours (float): Number of hours worked/leave.
                                - contract_id (int): ID of the related contract.

            Example:
                >>> self.get_worked_day_lines(contracts, '2025-08-01', '2025-08-31')
                [
                    {
                        'name': 'Normal Working Days paid at 100%',
                        'sequence': 1,
                        'code': 'WORK100',
                        'number_of_days': 22.0,
                        'number_of_hours': 176.0,
                        'contract_id': 5
                    },
                    {
                        'name': 'Paid Time Off',
                        'sequence': 5,
                        'code': 'PTO',
                        'number_of_days': -2.0,
                        'number_of_hours': -16.0,
                        'contract_id': 5
                    }
                ]
            """
        res = []
        # fill only if the contract as a working schedule linked
        for contract in contracts.filtered(lambda contract: contract.resource_calendar_id):
            day_from = datetime.combine(fields.Date.from_string(date_from), time.min)
            day_to = datetime.combine(fields.Date.from_string(date_to), time.max)

            # compute leave days
            leaves = {}
            calendar = contract.resource_calendar_id
            tz = timezone(calendar.tz)
            day_leave_intervals = contract.employee_id.list_leaves(day_from, day_to, calendar=contract.resource_calendar_id)
            for day, hours, leave in day_leave_intervals:
                holiday = leave.holiday_id
                current_leave_struct = leaves.setdefault(holiday.holiday_status_id, {
                    'name': holiday.holiday_status_id.name or _('Global Leaves'),
                    'sequence': 5,
                    'code': holiday.holiday_status_id.code or 'GLOBAL',
                    'number_of_days': 0.0,
                    'number_of_hours': 0.0,
                    'contract_id': contract.id,
                })
                current_leave_struct['number_of_hours'] -= hours
                work_hours = calendar.get_work_hours_count(
                    tz.localize(datetime.combine(day, time.min)),
                    tz.localize(datetime.combine(day, time.max)),
                    compute_leaves=False,
                )
                if work_hours:
                    current_leave_struct['number_of_days'] -= hours / work_hours

            # compute worked days
            work_data = contract.employee_id._get_work_days_data(
                day_from,
                day_to,
                calendar=contract.resource_calendar_id,
                compute_leaves=False,
            )
            attendances = {
                'name': _("Normal Working Days paid at 100%"),
                'sequence': 1,
                'code': 'WORK100',
                'number_of_days': work_data['days'],
                'number_of_hours': work_data['hours'],
                'contract_id': contract.id,
            }

            res.append(attendances)
            res.extend(leaves.values())
        return res

    @api.model
    def get_inputs(self, contracts):
        """
            Compute and return input lines for the given contracts
             within a payslip period.

            This method retrieves all salary rule structures associated
             with the given contracts,
            extracts their corresponding salary rules, and collects the
             linked input definitions.
            For each contract, it generates a list of input entries that
             can be used in the payslip computation.

            Args:
                contracts (recordset of hr.contract): Contracts to process
                 for input lines.

            Returns:
                list[dict]:
                    A list of dictionaries, where each dictionary represents
                     an input line with:
                        - name (str): Input name defined in salary rule.
                        - code (str): Input code used for identification.
                        - contract_id (int): ID of the related contract.

            Example:
                >>> self.get_inputs(contracts, '2025-08-01', '2025-08-31')
                [
                    {'name': 'Meal Voucher', 'code': 'MEAL', 'contract_id': 7},
                    {'name': 'Transport Allowance', 'code': 'TRANS', 'contract_id': 7},
                    ...
                ]
            """
        res = []

        structure_ids = contracts.get_all_structures()
        rule_ids = self.env['hr.payroll.structure'].browse(structure_ids).get_all_rules()
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x:x[1])]
        inputs = self.env['hr.salary.rule'].browse(sorted_rule_ids).mapped('input_ids')

        for contract in contracts:
            for input in inputs:
                input_data = {
                    'name': input.name,
                    'code': input.code,
                    'contract_id': contract.id,
                }
                res += [input_data]
        return res

    @api.model
    def _get_payslip_lines(self, contract_ids, payslip_id):
        """
        Compute the payslip lines (salary rule results) for the given
         contracts and payslip.

        This method evaluates salary rules linked to the contracts
         and the related payroll structures to generate line items
          (earnings, deductions, contributions, etc.)that will appear
           on the payslip. The rules are executed in sequence order,
            and conditions are verified before computing amounts.

        It also leverages helper classes (
        `BrowsableObject`, `InputLine`, `WorkedDays`, `Payslips`)
        that allow salary rules' Python expressions to access
         worked days, inputs, previous payslip data,
          and categories dynamically.

        Args:
            contract_ids (list[int]): List of hr.contract
             record IDs to consider.
            payslip_id (int): ID of the hr.payslip for
             which lines are being computed.

        Returns:
            list[dict]:
                A list of dictionaries representing computed
                 salary rule lines.
                Each dictionary contains:
                    - salary_rule_id (int): ID of the salary
                     rule applied.
                    - contract_id (int): Related contract ID.
                    - name (str): Salary rule name.
                    - code (str): Rule code (unique identifier
                     used in calculations).
                    - category_id (int): Salary category ID.
                    - sequence (int): Execution order of the rule.
                    - appears_on_payslip (bool): Whether the rule
                     should appear on the payslip.
                    - condition_select / condition_python / condition_range
                     / condition_range_min / condition_range_max:
                        Rule condition configuration.
                    - amount_select / amount_fix / amount_python_compute
                     / amount_percentage / amount_percentage_base:
                        Rule amount configuration.
                    - register_id (int): Related register
                     (e.g., tax or contribution).
                    - amount (float): Computed rule amount.
                    - employee_id (int): Employee linked to the contract.
                    - quantity (float): Quantity used in calculation.
                    - rate (float): Percentage rate applied.

        Note:
            - Rules are executed in order of their sequence.
            - If a rule condition is not satisfied, that rule and
             its children are blacklisted (ignored).
            - Categories accumulate amounts across rules for reporting purposes.
            - Inputs, worked days, and previous payslip results are
             available inside rule formulas.

        Example:
            >>> self._get_payslip_lines([12, 13], 45)
            [
                {
                    'salary_rule_id': 5,
                    'contract_id': 12,
                    'name': 'Basic Salary',
                    'code': 'BASIC',
                    'category_id': 2,
                    'sequence': 100,
                    'appears_on_payslip': True,
                    'amount': 1500.0,
                    'employee_id': 7,
                    'quantity': 1.0,
                    'rate': 100.0,
                    ...
                },
                ...
            ]
        """

        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                category.parent_id: localdict = _sum_salary_rule_category(
                    localdict, category.parent_id, amount)
                localdict['categories'].dict[category.code] =\
                    (category.code in localdict['categories'].dict and
                     localdict['categories'].dict[category.code] + amount or amount)
            return localdict

        class BrowsableObject(object):
            """Wrapper object to expose computed values
             (rules, categories, inputs, worked days)
              in salary rule Python code.
            """

            def __init__(self, employee_id, dict, env):
                self.employee_id = employee_id
                self.dict = dict
                self.env = env

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0

        class InputLine(BrowsableObject):
            """Helper to access input lines
             (custom allowances/deductions)
              by code inside rules.
              """
            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = fields.Date.today()
                self.env.cr.execute(
                    """ SELECT sum(amount) as sum FROM hr_payslip as hp,
                    hr_payslip_input as pi WHERE hp.employee_id = %s AND
                    hp.state = 'done' AND hp.date_from >= %s AND
                    hp.date_to <= %s AND hp.id = pi.payslip_id AND
                    pi.code = %s""",
                    (self.employee_id, from_date, to_date, code))
                return self.env.cr.fetchone()[0] or 0.0

        class WorkedDays(BrowsableObject):
            """Helper to access worked days and leave days by code inside rules."""

            def _sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = fields.Date.today()
                self.env.cr.execute(
                    """ SELECT sum(number_of_days) as number_of_days,
                    sum(number_of_hours) as number_of_hours FROM hr_payslip as hp,
                    hr_payslip_worked_days as pi WHERE hp.employee_id = %s AND
                    hp.state = 'done' AND hp.date_from >= %s AND
                    hp.date_to <= %s AND hp.id = pi.payslip_id AND pi.code = %s""",
                    (self.employee_id, from_date, to_date, code))
                return self.env.cr.fetchone()

            def sum(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[0] or 0.0

            def sum_hours(self, code, from_date, to_date=None):
                res = self._sum(code, from_date, to_date)
                return res and res[1] or 0.0

        class Payslips(BrowsableObject):
            """Helper to access past payslip results by rule code inside salary rules."""

            def sum(self, code, from_date, to_date=None):
                if to_date is None:
                    to_date = fields.Date.today()
                self.env.cr.execute(
                    """SELECT sum(case when hp.credit_note = False
                    then (pl.total) else (-pl.total) end) FROM
                    hr_payslip as hp, hr_payslip_line as pl WHERE
                    hp.employee_id = %s AND hp.state = 'done' AND
                    hp.date_from >= %s AND hp.date_to <= %s AND
                    hp.id = pl.slip_id AND pl.code = %s""",
                    (self.employee_id, from_date, to_date, code)
                )
                res = self.env.cr.fetchone()
                return res and res[0] or 0.0

        #we keep a dict with the result because a value can be overwritten by another rule with the same code
        result_dict = {}
        rules_dict = {}
        worked_days_dict = {}
        inputs_dict = {}
        blacklist = []
        payslip = self.env['hr.payslip'].browse(payslip_id)
        for worked_days_line in payslip.worked_days_line_ids:
            worked_days_dict[worked_days_line.code] = worked_days_line
        for input_line in payslip.input_line_ids:
            inputs_dict[input_line.code] = input_line

        categories = BrowsableObject(payslip.employee_id.id, {}, self.env)
        inputs = InputLine(payslip.employee_id.id, inputs_dict, self.env)
        worked_days = WorkedDays(payslip.employee_id.id, worked_days_dict, self.env)
        payslips = Payslips(payslip.employee_id.id, payslip, self.env)
        rules = BrowsableObject(payslip.employee_id.id, rules_dict, self.env)

        baselocaldict = {
            'categories': categories,
            'rules': rules,
            'payslip': payslips,
            'worked_days': worked_days,
            'inputs': inputs
        }

        #get the ids of the structures on the contracts and their parent id as well
        contracts = self.env['hr.contract'].browse(contract_ids)
        if len(contracts) == 1 and payslip.struct_id:
            structure_ids = list(set(payslip.struct_id._get_parent_structure().ids))
        else:
            structure_ids = contracts.get_all_structures()
        #get the rules of the structure and thier children
        rule_ids = self.env['hr.payroll.structure'].browse(structure_ids).get_all_rules()
        #run the rules by sequence
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x:x[1])]
        sorted_rules = self.env['hr.salary.rule'].browse(sorted_rule_ids)

        for contract in contracts:
            employee = contract.employee_id
            localdict = dict(baselocaldict, employee=employee, contract=contract)
            for rule in sorted_rules:
                key = rule.code + '-' + str(contract.id)
                localdict['result'] = None
                localdict['result_qty'] = 1.0
                localdict['result_rate'] = 100
                #check if the rule can be applied
                if rule._satisfy_condition(localdict) and rule.id not in blacklist:
                    #compute the amount of the rule
                    amount, qty, rate = rule._compute_rule(localdict)
                    #check if there is already a rule computed with that code
                    previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                    #set/overwrite the amount computed for this rule in the localdict
                    tot_rule = contract.company_id.currency_id.round(amount * qty * rate / 100.0)
                    localdict[rule.code] = tot_rule
                    rules_dict[rule.code] = rule
                    #sum the amount for its salary category
                    localdict = _sum_salary_rule_category(localdict, rule.category_id, tot_rule - previous_amount)
                    #create/overwrite the rule in the temporary results
                    result_dict[key] = {
                        'salary_rule_id': rule.id,
                        'contract_id': contract.id,
                        'name': rule.name,
                        'code': rule.code,
                        'category_id': rule.category_id.id,
                        'sequence': rule.sequence,
                        'appears_on_payslip': rule.appears_on_payslip,
                        'condition_select': rule.condition_select,
                        'condition_python': rule.condition_python,
                        'condition_range': rule.condition_range,
                        'condition_range_min': rule.condition_range_min,
                        'condition_range_max': rule.condition_range_max,
                        'amount_select': rule.amount_select,
                        'amount_fix': rule.amount_fix,
                        'amount_python_compute': rule.amount_python_compute,
                        'amount_percentage': rule.amount_percentage,
                        'amount_percentage_base': rule.amount_percentage_base,
                        'register_id': rule.register_id.id,
                        'amount': amount,
                        'employee_id': contract.employee_id.id,
                        'quantity': qty,
                        'rate': rate,
                    }
                else:
                    #blacklist this rule and its children
                    blacklist += [id for id, seq in rule._recursive_search_of_rules()]

        return list(result_dict.values())

    # YTI TODO To rename. This method is not really an onchange, as it is not in any view
    # employee_id and contract_id could be browse records
    def onchange_employee_id(self, date_from, date_to, employee_id=False, contract_id=False):
        """
            Handle changes when an employee is selected in the payslip form.

            This method prepares default values for a payslip when the employee,
            contract, or date range is updated. It:
              - Clears old input and worked days lines.
              - Sets the payslip name, company, contract, and structure.
              - Computes and attaches new worked days and input lines for the selected employee
                based on the given date range and contracts.

            Args:
                date_from (str): The start date of the payslip period (YYYY-MM-DD).
                date_to (str): The end date of the payslip period (YYYY-MM-DD).
                employee_id (int, optional): ID of the employee linked to the payslip.
                contract_id (int, optional): Specific contract ID if provided, otherwise
                                             determines active contracts in the date range.

            Returns:
                dict: A dictionary containing updated values for the payslip fields,
                      including contract, structure, worked days, and input lines.
        """
        #defaults
        res = {
            'value': {
                'line_ids': [],
                #delete old input lines
                'input_line_ids': [(2, x,) for x in self.input_line_ids.ids],
                #delete old worked days lines
                'worked_days_line_ids': [(2, x,) for x in self.worked_days_line_ids.ids],
                #'details_by_salary_head':[], TODO put me back
                'name': '',
                'contract_id': False,
                'struct_id': False,
            }
        }
        if (not employee_id) or (not date_from) or (not date_to):
            return res
        ttyme = datetime.combine(fields.Date.from_string(date_from), time.min)
        employee = self.env['hr.employee'].browse(employee_id)
        locale = self.env.context.get('lang') or 'en_US'
        res['value'].update({
            'name': _('Salary Slip of %s for %s') % (employee.name, tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale))),
            'company_id': employee.company_id.id,
        })

        if not self.env.context.get('contract'):
            #fill with the first contract of the employee
            contract_ids = self.get_contract(employee, date_from, date_to)
        else:
            if contract_id:
                #set the list of contract for which the input have to be filled
                contract_ids = [contract_id]
            else:
                #if we don't give the contract, then the input to fill should be for all current contracts of the employee
                contract_ids = self.get_contract(employee, date_from, date_to)

        if not contract_ids:
            return res
        contract = self.env['hr.contract'].browse(contract_ids[0])
        res['value'].update({
            'contract_id': contract.id
        })
        struct = contract.struct_id
        if not struct:
            return res
        res['value'].update({
            'struct_id': struct.id,
        })
        #computation of the salary input
        contracts = self.env['hr.contract'].browse(contract_ids)
        worked_days_line_ids = self.get_worked_day_lines(contracts, date_from, date_to)
        input_line_ids = self.get_inputs(contracts, date_from, date_to)
        res['value'].update({
            'worked_days_line_ids': worked_days_line_ids,
            'input_line_ids': input_line_ids,
        })
        return res

    @api.onchange('employee_id', 'date_from', 'date_to')
    def onchange_employee(self):
        self.ensure_one()
        if (not self.employee_id) or (not self.date_from) or (not self.date_to):
            return
        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to
        contract_ids = []

        ttyme = datetime.combine(fields.Date.from_string(date_from), time.min)
        locale = self.env.context.get('lang') or 'en_US'
        self.name = _('Salary Slip of %s for %s') % (employee.name, tools.ustr(babel.dates.format_date(date=ttyme, format='MMMM-y', locale=locale)))
        self.company_id = employee.company_id

        if not self.env.context.get('contract') or not self.contract_id:
            contract_ids = self.get_contract(employee, date_from, date_to)
            if not contract_ids:
                return
            self.contract_id = self.env['hr.contract'].browse(contract_ids[0])

        if not self.contract_id.struct_id:
            return
        self.struct_id = self.contract_id.struct_id

        #computation of the salary input
        contracts = self.env['hr.contract'].browse(contract_ids)
        if contracts:
            worked_days_line_ids = self.get_worked_day_lines(contracts, date_from, date_to)
            worked_days_lines = self.worked_days_line_ids.browse([])
            for r in worked_days_line_ids:
                worked_days_lines += worked_days_lines.new(r)
            self.worked_days_line_ids = worked_days_lines

            input_line_ids = self.get_inputs(contracts, date_from, date_to)
            input_lines = self.input_line_ids.browse([])
            for r in input_line_ids:
                input_lines += input_lines.new(r)
            self.input_line_ids = input_lines
            return

    @api.onchange('contract_id')
    def onchange_contract(self):
        if not self.contract_id:
            self.struct_id = False
        self.with_context(contract=True).onchange_employee()
        return

    def get_salary_line_total(self, code):
        self.ensure_one()
        line = self.line_ids.filtered(lambda line: line.code == code)
        if line:
            return line[0].total
        else:
            return 0.0


class HrPayslipLine(models.Model):
    """
    Represents a detailed line item of an employee payslip.

    This model stores the result of applying a salary rule to a contract
    for a given payslip. Each payslip line records calculated values such as
    quantity, amount, rate, and the resulting total.

    It inherits from `hr.salary.rule` to reuse the definition and properties
    of salary rules (code, category, sequence, etc.).
    """
    _name = 'hr.payslip.line'
    _inherit = 'hr.salary.rule'
    _description = 'Employee Payslip Line Item'
    _order = 'contract_id, sequence'

    # ==========================
    # Fields
    # ==========================
    slip_id = fields.Many2one(
        'hr.payslip',
        string='Pay Slip',
        required=True,
        ondelete='cascade',
        help="The payslip to which this line belongs."
    )
    salary_rule_id = fields.Many2one(
        'hr.salary.rule',
        string='Salary Rule',
        required=True,
        help="The salary rule applied to generate this payslip line."
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        help="The employee for whom this payslip line is generated."
    )
    contract_id = fields.Many2one(
        'hr.contract',
        string='Contract',
        required=True,
        index=True,
        help="The contract used to compute this payslip line."
    )
    rate = fields.Float(
        string='Rate (%)',
        default=100.0,
        help="Percentage rate applied on the calculated amount."
    )
    amount = fields.Float(
        string='Amount',
        help="The base amount defined by the salary rule."
    )
    quantity = fields.Float(
        string='Quantity',
        default=1.0,
        help="The number of units used for calculation (e.g., days, hours)."
    )
    total = fields.Float(
        compute='_compute_total',
        string='Total',
        help="The computed total = Quantity * Amount * Rate / 100."
    )

    # ==========================
    # Compute Methods
    # ==========================
    @api.depends('quantity', 'amount', 'rate')
    def _compute_total(self):
        """
        Compute the total amount for each payslip line.

        Formula:
            total = quantity * amount * rate / 100
        """
        for line in self:
            line.total = float(line.quantity) * line.amount * line.rate / 100

    # ==========================
    # ORM Overrides
    # ==========================
    @api.model_create_multi
    def create(self, vals_list):
        """
        Override create method to ensure `employee_id` and `contract_id`
        are properly set when creating a payslip line.

        - If not provided, they are taken from the linked payslip (`slip_id`).
        - Raises an error if no contract is found.

        :param vals_list: List of dictionaries with field values.
        :return: Recordset of created `hr.payslip.line` records.
        """
        for values in vals_list:
            if 'employee_id' not in values or 'contract_id' not in values:
                payslip = self.env['hr.payslip'].browse(values.get('slip_id'))
                values['employee_id'] = (values.get('employee_id')
                                         or payslip.employee_id.id)
                values['contract_id'] = (values.get('contract_id')
                                         or (payslip.contract_id
                                             and payslip.contract_id.id))
                if not values['contract_id']:
                    raise UserError(_(
                        'You must set a contract to create a payslip line.'
                    ))
        return super(HrPayslipLine, self).create(vals_list)


class HrPayslipWorkedDays(models.Model):
    _name = 'hr.payslip.worked_days'
    _description = 'Payslip Worked Days'
    _order = 'payslip_id, sequence'

    name = fields.Char(string='Description', required=True)
    payslip_id = fields.Many2one('hr.payslip', string='Pay Slip',
                                 required=True, ondelete='cascade',
                                 index=True)
    sequence = fields.Integer(required=True, index=True, default=10)
    code = fields.Char(required=True, help="The code that can be used in the salary rules")
    number_of_days = fields.Float(string='Number of Days')
    number_of_hours = fields.Float(string='Number of Hours')
    contract_id = fields.Many2one('hr.contract', string='Contract', required=True,
        help="The contract for which applied this input")


class HrPayslipInput(models.Model):
    _name = 'hr.payslip.input'
    _description = 'Payslip Input'
    _order = 'payslip_id, sequence'

    name = fields.Char(string='Description', required=True)
    payslip_id = fields.Many2one(
        'hr.payslip', string='Pay Slip',
        required=True, ondelete='cascade',
        index=True
    )
    sequence = fields.Integer(required=True, index=True, default=10)
    code = fields.Char(required=True, help="The code that can be used in the salary rules")
    amount = fields.Float(
        help="It is used in computation. For e.g. A rule for sales having 1% commission of"
             " basic salary for per product can defined in expression like"
             " result = inputs.SALEURO.amount * contract.wage*0.01.",
        strin="Amount"
    )
    contract_id = fields.Many2one(
        'hr.contract', string='Contract', required=True,
        help="The contract for which applied this input"
    )


class HrPayslipRun(models.Model):
    """
    Model representing a batch of payslips.

    A Payslip Run (also known as Payslip Batch) groups multiple payslips for
    a specific period. It allows payroll managers to manage, confirm, and
    close payslips in bulk for a defined time range.

    States:
        - draft: Batch is in preparation (editable).
        - done: All payslips in the batch are confirmed.
        - close: Batch is finalized and closed.
    """
    _name = 'hr.payslip.run'
    _description = 'Payslip Run / Batch'

    # =========================
    # Fields
    # =========================
    name = fields.Char(
        string="Batch Name",
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        help="Name of the payslip batch (e.g., August 2025 Payroll)."
    )
    slip_ids = fields.One2many(
        'hr.payslip',
        'payslip_run_id',
        string='Payslips',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help="List of payslips associated with this batch."
    )
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('done', 'Done'),
            ('close', 'Close'),
        ],
        string='Status',
        index=True,
        readonly=True,
        copy=False,
        default='draft',
        help="Current status of the payslip batch."
    )
    date_start = fields.Date(
        string='Start Date',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        default=lambda self: fields.Date.to_string(date.today().replace(day=1)),
        help="The start date of the payslip batch period."
    )
    date_end = fields.Date(
        string='End Date',
        required=True,
        readonly=True,
        states={'draft': [('readonly', False)]},
        default=lambda self: fields.Date.to_string(
            (datetime.now() + relativedelta(months=+1, day=1, days=-1)).date()
        ),
        help="The end date of the payslip batch period."
    )
    credit_note = fields.Boolean(
        string='Credit Note',
        readonly=True,
        states={'draft': [('readonly', False)]},
        help="If enabled, all payslips generated in this batch are refund payslips."
    )

    # =========================
    # Business Logic
    # =========================
    def draft_payslip_run(self):
        """
        Reset the batch state back to 'Draft'.
        This allows editing and regeneration of payslips in the batch.
        """
        return self.write({'state': 'draft'})

    def close_payslip_run(self):
        """
        Mark the payslip batch as 'Close'.
        This finalizes the batch and prevents further modifications.
        """
        return self.write({'state': 'close'})

    def done_payslip_run(self):
        """
        Mark the payslip batch as 'Done'.
        This confirms all payslips in the batch before updating the batch state.
        """
        for line in self.slip_ids:
            line.action_payslip_done()
        return self.write({'state': 'done'})

    def unlink(self):
        """
        Restrict deletion of completed payslip batches.

        Raises:
            ValidationError: If an attempt is made to delete a batch
                             with state 'done'.
        """
        for rec in self:
            if rec.state == 'done':
                raise ValidationError(_('You cannot delete a completed payslip batch.'))
        return super(HrPayslipRun, self).unlink()
