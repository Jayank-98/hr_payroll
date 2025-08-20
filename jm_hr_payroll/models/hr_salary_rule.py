# -*- coding:utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrPayrollStructure(models.Model):
    """
    Salary Structure model to define payroll structure with rules and hierarchy.
    """
    _name = 'hr.payroll.structure'
    _description = 'Salary Structure'

    @api.model
    def _get_parent(self):
        """Get default base parent salary structure (if available)."""
        return self.env.ref('om_jm_hr_payroll.structure_base', False)

    # Basic Details
    name = fields.Char(string="Name", required=True, help="Name of the salary structure.")
    code = fields.Char(string="Reference", required=True, help="Unique reference code for the salary structure.")
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help="Company to which this salary structure belongs."
    )
    note = fields.Text(string='Description', help="Additional details about the salary structure.")

    # Relations
    parent_id = fields.Many2one(
        'hr.payroll.structure',
        string='Parent',
        default=_get_parent,
        help="Parent salary structure from which rules can be inherited."
    )
    children_ids = fields.One2many(
        'hr.payroll.structure',
        'parent_id',
        string='Children',
        copy=True,
        help="Child salary structures linked to this structure."
    )
    rule_ids = fields.Many2many(
        'hr.salary.rule',
        'hr_structure_salary_rule_rel',
        'struct_id',
        'rule_id',
        string='Salary Rules',
        help="Salary rules that are part of this structure."
    )

    @api.constrains('parent_id')
    def _check_parent_id(self):
        """Validate that no recursive parent-child relation exists."""
        if not self._check_recursion():
            raise ValidationError(_('You cannot create a recursive salary structure.'))

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        """
        Duplicate salary structure with updated code.
        """
        self.ensure_one()
        default = dict(default or {}, code=_("%s (copy)") % (self.code))
        return super(HrPayrollStructure, self).copy(default)

    def get_all_rules(self):
        """
        Return all salary rules (id, sequence) recursively linked to this structure.
        """
        all_rules = []
        for struct in self:
            all_rules += struct.rule_ids._recursive_search_of_rules()
        return all_rules

    def _get_parent_structure(self):
        """
        Recursively fetch all parent structures and return with current one.
        """
        parent = self.mapped('parent_id')
        if parent:
            parent = parent._get_parent_structure()
        return parent + self


class HrContributionRegister(models.Model):
    """
    Contribution Register Model

    Represents a register that tracks payroll contributions (e.g., PF, ESIC,
    or other statutory deductions/benefits). Each register can be linked
    to a company, a partner, and payslip lines.
    """
    _name = 'hr.contribution.register'
    _description = 'Contribution Register'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help="The company this contribution register belongs to."
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        help="The third-party (like government agency, bank, etc.) "
             "to whom the contribution is payable."
    )
    name = fields.Char(
        string='Register Name',
        required=True,
        help="Name of the contribution register (e.g., PF Register, ESIC Register)."
    )
    register_line_ids = fields.One2many(
        'hr.payslip.line',
        'register_id',
        string='Register Lines',
        readonly=True,
        help="Payslip lines that are linked to this contribution register."
    )
    note = fields.Text(
        string='Description',
        help="Additional information or notes about this contribution register."
    )


class HrSalaryRuleCategory(models.Model):
    """
    Salary Rule Category Model

    Represents categories used to group salary rules in payroll.
    Categories can be hierarchical (parent/child) and are mainly
    used for reporting and structuring payroll computations.
    """
    _name = 'hr.salary.rule.category'
    _description = 'Salary Rule Category'

    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True,
        help="Name of the salary rule category (e.g., Allowances, Deductions)."
    )
    code = fields.Char(
        string='Code',
        required=True,
        help="Unique code to identify this salary rule category."
    )
    parent_id = fields.Many2one(
        'hr.salary.rule.category',
        string='Parent',
        help="Optional parent category. Used only for reporting hierarchy."
    )
    children_ids = fields.One2many(
        'hr.salary.rule.category',
        'parent_id',
        string='Children',
        help="Sub-categories belonging to this salary rule category."
    )
    note = fields.Text(
        string='Description',
        help="Additional notes or description for this salary rule category."
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help="Company to which this salary rule category belongs."
    )

    @api.constrains('parent_id')
    def _check_parent_id(self):
        """
        Constraint to prevent recursive hierarchy.

        Ensures that a salary rule category cannot be its own
        ancestor or descendant (avoiding infinite loops).
        """
        if not self._check_recursion():
            raise ValidationError(
                _('Hierarchy not allowed: A Salary Rule Category can’t circle back to itself')
            )



class HrSalaryRule(models.Model):
    """
       Salary Rule Model

       Defines payroll rules such as allowances, deductions, or contributions.
       Each rule determines how amounts are calculated based on fixed values,
       percentages, or custom Python expressions.
   """
    _name = 'hr.salary.rule'
    _order = 'sequence, id'
    _description = 'Salary Rule'

    name = fields.Char(
        string='Rule Name',
        required=True,
        translate=True,
        help="Name of the salary rule (e.g., Basic, HRA, PF)."
    )
    code = fields.Char(
        string='Code',
        required=True,
        help="Unique code for the rule, used as a reference in other computations. "
             "This field is case sensitive."
    )
    sequence = fields.Integer(
        string='Sequence',
        required=True,
        index=True,
        default=5,
        help='Determines the order in which rules are applied during computation.'
    )
    quantity = fields.Char(
        string='Quantity',
        default='1.0',
        help="Factor applied to the rule (e.g., worked days). "
             "Can be expressed using formulas like worked_days.WORK100.number_of_days."
    )
    category_id = fields.Many2one(
        'hr.salary.rule.category',
        string='Category',
        required=True,
        help="Defines the salary rule category (e.g., Allowances, Deductions)."
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help="If unchecked, the rule will be hidden without being deleted."
    )
    appears_on_payslip = fields.Boolean(
        string='Appears on Payslip',
        default=True,
        help="If enabled, the rule will be displayed on payslips."
    )
    parent_rule_id = fields.Many2one(
        'hr.salary.rule',
        string='Parent Salary Rule',
        index=True,
        help="Optional parent salary rule. Useful for hierarchical grouping of rules."
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help="Company associated with this salary rule."
    )
    condition_select = fields.Selection([
        ('none', 'Always True'),
        ('range', 'Range'),
        ('python', 'Python Expression')
    ], string="Condition Based on", default='none', required=True,
        help="Determines when this rule should be applied:"
             " always, by range, or using Python expression."
    )
    condition_range = fields.Char(
        string='Range Based on',
        default='contract.wage',
        help='Expression to compute the range value (e.g., contract.wage). '
             'Can also use salary categories codes (hra, ma, lta, etc.).'
    )
    condition_python = fields.Text(
        string='Python Condition',
        required=True,
        default='''
        # Available variables:
        # payslip, employee, contract, rules, categories, worked_days, inputs
        # result must be set to True/False
                        
        result = rules.NET > categories.NET * 0.10''',
        help='Python expression returning True if the rule should apply, else False.'
    )
    condition_range_min = fields.Float(
        string='Minimum Range',
        help="Lower bound of range condition."
    )
    condition_range_max = fields.Float(
        string='Maximum Range',
        help="Upper bound of range condition."
    )
    amount_select = fields.Selection([
        ('percentage', 'Percentage (%)'),
        ('fix', 'Fixed Amount'),
        ('code', 'Python Code'),
    ], string='Amount Type', index=True, required=True, default='fix',
        help="Defines how the rule amount is calculated."
    )
    amount_fix = fields.Float(
        string='Fixed Amount',
        help="Fixed amount applied for this rule (if amount type = Fixed)."
    )
    amount_percentage = fields.Float(
        string='Percentage (%)',
        help='Percentage to apply (e.g., 50.0 for 50%).'
    )
    amount_python_compute = fields.Text(
        string='Python Code',
        default='''
                        # Available variables:
                        # payslip, employee, contract, rules, categories, worked_days, inputs
                        # result must be set as the computed amount

                        result = contract.wage * 0.10''',
        help="Python code used to compute the rule amount dynamically."
    )
    amount_percentage_base = fields.Char(
        string='Percentage Based On',
        help='Expression used as base for percentage calculation.'
    )
    child_ids = fields.One2many(
        'hr.salary.rule', 'parent_rule_id',
        string='Child Salary Rule', copy=True,
        help="Sub-rules belonging to this salary rule."
    )
    register_id = fields.Many2one(
        'hr.contribution.register',
        string='Contribution Register',
        help="Optional register for third-party contributions (e.g., PF, ESIC)."
    )
    input_ids = fields.One2many(
        'hr.rule.input', 'input_id',
        string='Inputs', copy=True,
        help="Inputs linked to this salary rule (e.g., meal vouchers, overtime)."
    )
    note = fields.Text(
        string='Description',
        help="Additional notes or details about this rule."
    )

    @api.constrains('parent_rule_id')
    def _check_parent_rule_id(self):
        """
            Constraint to prevent recursive hierarchy of salary rules.
            Ensures a rule cannot be its own ancestor or descendant.
        """
        if not self._check_recursion(parent='parent_rule_id'):
            raise ValidationError(_(
                'Invalid setup — a Salary Rule can’t be both parent and child.'
            ))

    def _recursive_search_of_rules(self):
        """
        Recursively collects salary rules.

        :return: List of tuples (rule_id, sequence) including this rule and all children.
        """
        children_rules = []
        for rule in self.filtered(lambda rule: rule.child_ids):
            children_rules += rule.child_ids._recursive_search_of_rules()
        return [(rule.id, rule.sequence) for rule in self] + children_rules

    def _compute_rule(self, localdict):
        """
            Compute the rule amount.

            :param localdict: Environment dictionary (payslip, employee, contract, etc.)
            :return: (base, quantity, rate)
            :rtype: (float, float, float)
        """
        self.ensure_one()
        if self.amount_select == 'fix':
            try:
                return self.amount_fix, float(safe_eval(self.quantity, localdict)), 100.0
            except:
                raise UserError(
                    _(
                        'Wrong quantity defined for salary rule %s (%s).'
                    ) % (self.name, self.code)
                )
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
                return (
                    float(localdict['result']), 'result_qty' in localdict and
                    localdict['result_qty'] or 1.0, 'result_rate' in localdict and
                    localdict['result_rate'] or 100.0
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
            Check whether the rule satisfies its condition.

            :param localdict: Environment dictionary
            :return: True if rule condition passes, otherwise False
            :rtype: bool
        """
        self.ensure_one()

        if self.condition_select == 'none':
            return True
        elif self.condition_select == 'range':
            try:
                result = safe_eval(self.condition_range, localdict)
                return (self.condition_range_min <= result and
                        result <= self.condition_range_max or False)
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
    """Defines input values linked to salary rules."""
    _name = 'hr.rule.input'
    _description = 'Salary Rule Input'

    name = fields.Char(string='Description', required=True)
    code = fields.Char(
        string="Code",
        required=True,
        help="The code that can be used in the salary rules"
    )
    input_id = fields.Many2one(
        'hr.salary.rule',
        string='Salary Rule Input',
        required=True
    )
