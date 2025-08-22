# -*- coding:utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class HrPayrollStructure(models.Model):
    """
        Defines the salary structure of employees.

        Purpose:
        - Groups basic, allowances, and deduction salary rules.
        - Supports parent/child structures for hierarchical pay setups.
        - Provides all salary rules for payslip computations.
    """
    _name = 'hr.payroll.structure'
    _description = 'Employee Salary Structure'

    @api.model
    def _get_parent(self):
        """Fetch the default parent salary structure (base structure)."""
        return self.env.ref('om_jm_hr_payroll.payroll_structure_base', False)

    # Basic structure details
    name = fields.Char(required=True)
    code = fields.Char(string='Reference', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company',
        required=True, default=lambda self: self.env.company
    )

    # Hierarchy
    note = fields.Text(string='Description')
    parent_id = fields.Many2one(
        'hr.payroll.structure',
        string='Parent', default=_get_parent
    )
    children_ids = fields.One2many(
        'hr.payroll.structure', 'parent_id',
        string='Children', copy=True
    )


    # Related salary rules
    rule_ids = fields.Many2many(
        'hr.salary.rule', 'hr_structure_salary_rule_rel',
        'struct_id', 'rule_id', string='Salary Rules'
    )

    @api.constrains('parent_id')
    def _check_parent_id(self):
        """Prevent recursive parent structure assignment."""
        if not self._check_recursion():
            raise ValidationError(_('You cannot create a recursive salary structure.'))

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        """Duplicate salary structure with updated reference code."""
        self.ensure_one()
        default = dict(default or {}, code=_("%s (copy)") % (self.code))
        return super(HrPayrollStructure, self).copy(default)

    def get_all_rules(self):
        """
            Get all salary rules linked to this structure.

            :return: list of tuples (id, sequence) for rules.
        """
        all_rules = []
        for struct in self:
            all_rules += struct.rule_ids._recursive_search_of_rules()
        return all_rules

    def _get_parent_structure(self):
        """Recursively fetch all parent structures."""
        parent = self.mapped('parent_id')
        if parent:
            parent = parent._get_parent_structure()
        return parent + self


class HrContributionRegister(models.Model):
    """
        Register for contribution rules.

        Purpose:
        - Tracks contribution entities (e.g., PF, ESI, tax).
        - Links contribution details with payslip lines.
    """
    _name = 'hr.contribution.register'
    _description = 'Contribution Register for Salary Payments'

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company
    )
    partner_id = fields.Many2one('res.partner', string='Partner')
    name = fields.Char(required=True)
    register_line_ids = fields.One2many('hr.payslip.line', 'register_id',
        string='Register Line', readonly=True)
    note = fields.Text(string='Description')


class HrSalaryRuleCategory(models.Model):
    """
    Categorization of salary rules.

    Purpose:
    - Groups rules under categories like Allowances, Deductions, Gross, Net.
    - Supports hierarchy for reporting and classification.
    """
    _name = 'hr.salary.rule.category'
    _description = 'Salary Rule Category (Allowance, Deduction, etc.)'

    name = fields.Char(required=True, translate=True, string="Name")
    code = fields.Char(required=True, string="Code")
    parent_id = fields.Many2one('hr.salary.rule.category', string='Parent',
        help="Defines hierarchy of salary categories for reporting.")
    children_ids = fields.One2many(
        'hr.salary.rule.category',
        'parent_id', string='Children'
    )
    note = fields.Text(string='Description')
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company
    )

    @api.constrains('parent_id')
    def _check_parent_id(self):
        """Prevent recursive category hierarchy."""
        if not self._check_recursion():
            raise ValidationError(_(
                'Error! You cannot create recursive hierarchy of Salary Rule Category.'
            ))


class HrSalaryRule(models.Model):
    """
    Defines a salary rule used in payroll computation.

    Purpose:
    - Represents individual earning/deduction rule (e.g., HRA, PF, Bonus).
    - Computes values using fixed, percentage, or Python logic.
    - Can have conditions and hierarchical child rules.
    """
    _name = 'hr.salary.rule'
    _order = 'sequence, id'
    _description = 'Salary Rule for Payroll Computation'

    # Basic rule details
    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True,
        help="The code of salary rules can be used as reference in computation of other rules. "
             "In that case, it is case sensitive.")
    sequence = fields.Integer(required=True, index=True, default=5,
        help='Use to arrange calculation sequence')

    # Computation base fields
    quantity = fields.Char(default='1.0',
        help="It is used in computation for percentage and fixed amount. "
             "For e.g. A rule for Meal Voucher having fixed amount of "
             u"1€ per worked day can have its quantity defined in expression "
             "like worked_days.WORK100.number_of_days.")
    category_id = fields.Many2one('hr.salary.rule.category', string='Category', required=True)
    active = fields.Boolean(default=True,
        help="If the active field is set to false, it will allow you to hide the salary rule without removing it.")
    appears_on_payslip = fields.Boolean(string='Appears on Payslip', default=True,
        help="Used to display the salary rule on payslip.")

    # Rule hierarchy
    parent_rule_id = fields.Many2one(
        'hr.salary.rule', string='Parent Salary Rule', index=True
    )

    # Company
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company
    )

    # Condition handling
    condition_select = fields.Selection([
        ('none', 'Always True'),
        ('range', 'Range'),
        ('python', 'Python Expression')
    ], string="Condition Based on", default='none', required=True)
    condition_range = fields.Char(string='Range Based on', default='contract.wage',
        help='This will be used to compute the % fields values; in general it is on basic, '
             'but you can also use categories code fields in lowercase as a variable names '
             '(hra, ma, lta, etc.) and the variable basic.')
    condition_python = fields.Text(string='Python Condition', required=True,
        default='''# Available variables:
        #----------------------
        # payslip: object containing the payslips
        # employee: hr.employee object
        # contract: hr.contract object
        # rules: object containing the rules code (previously computed)
        # categories: object containing the computed salary rule categories
         (sum of amount of all rules belonging to that category).
        # worked_days: object containing the computed worked days
        # inputs: object containing the computed inputs

        # Note: returned value have to be set in the variable 'result'

        result = rules.salary_rule_category_net > categories.salary_rule_category_net * 0.10''',
        help='Applied this rule for calculation if condition is true.'
             ' You can specify condition like basic > 1000.')
    condition_range_min = fields.Float(
        string='Minimum Range', help="The minimum amount, applied for this rule."
    )
    condition_range_max = fields.Float(
        string='Maximum Range', help="The maximum amount, applied for this rule."
    )
    amount_select = fields.Selection([
        ('percentage', 'Percentage (%)'),
        ('fix', 'Fixed Amount'),
        ('code', 'Python Code'),
    ], string='Amount Type', index=True, required=True, default='fix', help="The computation method for the rule amount.")
    amount_fix = fields.Float(string='Fixed Amount')
    amount_percentage = fields.Float(string='Percentage (%)',
        help='For example, enter 50.0 to apply a percentage of 50%')
    amount_python_compute = fields.Text(string='Python Code',
        default='''
                    # Available variables:
                    #----------------------
                    # payslip: object containing the payslips
                    # employee: hr.employee object
                    # contract: hr.contract object
                    # rules: object containing the rules code (previously computed)
                    # categories: object containing the computed salary rule categories (sum of amount of all rules belonging to that category).
                    # worked_days: object containing the computed worked days.
                    # inputs: object containing the computed inputs.

                    # Note: returned value have to be set in the variable 'result'

                    result = contract.wage * 0.10''')
    amount_percentage_base = fields.Char(
        string='Percentage based on',
        help='result will be affected to a variable'
    )
    child_ids = fields.One2many(
        'hr.salary.rule', 'parent_rule_id',
        string='Child Salary Rule', copy=True
    )

    # Other references
    register_id = fields.Many2one('hr.contribution.register', string='Contribution Register',
        help="Eventual third party involved in the salary payment of the employees.")
    input_ids = fields.One2many('hr.rule.input', 'input_id', string='Inputs', copy=True)
    note = fields.Text(string='Description')

    @api.constrains('parent_rule_id')
    def _check_parent_rule_id(self):
        """Prevent recursive parent-child salary rule hierarchy."""
        if not self._check_recursion(parent='parent_rule_id'):
            raise ValidationError(_(
                'Error! You cannot create recursive hierarchy of Salary Rules.'
            ))

    def _recursive_search_of_rules(self):
        """
            Recursively fetch all child salary rules.

            :return: list of tuples (rule_id, sequence)
        """
        children_rules = []
        for rule in self.filtered(lambda rule: rule.child_ids):
            children_rules += rule.child_ids._recursive_search_of_rules()
        return [(rule.id, rule.sequence) for rule in self] + children_rules

    def _compute_rule(self, localdict):
        """
            Compute the salary rule amount.

            :param localdict: dictionary containing evaluation context.
            :return: tuple (amount, quantity, rate).
        """
        self.ensure_one()
        if self.amount_select == 'fix':
            try:
                return self.amount_fix, float(safe_eval(self.quantity, localdict)), 100.0
            except:
                raise UserError(_(
                    'Wrong quantity defined for salary rule %s (%s).'
                ) % (self.name, self.code))
        elif self.amount_select == 'percentage':
            try:
                return (float(safe_eval(self.amount_percentage_base, localdict)),
                        float(safe_eval(self.quantity, localdict)),
                        self.amount_percentage)
            except:
                raise UserError(_(
                    'Wrong percentage base or quantity defined for salary rule %s (%s).'
                ) % (self.name, self.code))
        else:
            try:
                safe_eval(self.amount_python_compute, localdict, mode='exec', nocopy=True)
                return (float(localdict['result']), 'result_qty' in
                        localdict and localdict['result_qty'] or 1.0,
                        'result_rate' in localdict and localdict['result_rate'] or 100.0
                        )
            except Exception as ex:
                raise UserError(_(
                        """
                        Wrong python code defined for salary rule %s (%s).
                        Here is the error received:
                        %s
                        """
                    ) % (self.name, self.code, repr(ex)))

    def _satisfy_condition(self, localdict):
        """
            Check if rule condition is satisfied.

            :param localdict: evaluation context.
            :return: True if condition passes, else False.
        """
        self.ensure_one()

        if self.condition_select == 'none':
            return True
        elif self.condition_select == 'range':
            try:
                result = safe_eval(self.condition_range, localdict)
                return self.condition_range_min <= result <= self.condition_range_max or False
            except:
                raise UserError(_(
                    'Wrong range condition defined for salary rule %s (%s).'
                ) % (self.name, self.code))
        else:  # python code
            try:
                safe_eval(self.condition_python, localdict, mode='exec', nocopy=True)
                return 'result' in localdict and localdict['result'] or False
            except Exception as ex:
                raise UserError(_(
                        """
                        Wrong python condition defined for salary rule %s (%s).
                        Here is the error received:
                        %s
                        """
                    ) % (self.name, self.code, repr(ex)))


class HrRuleInput(models.Model):
    """
        Inputs linked to salary rules.

        Purpose:
        - Allows external/custom inputs (bonus, commission, etc.).
        - Referenced in salary rules by code.
    """
    _name = 'hr.rule.input'
    _description = 'Salary Rule Input (Custom Inputs for Rules)'

    name = fields.Char(string='Description', required=True)
    code = fields.Char(required=True, help="The code that can be used in the salary rules")
    input_id = fields.Many2one('hr.salary.rule', string='Salary Rule Input', required=True)
