# -*- coding:utf-8 -*-

from odoo import api, fields, models


class HrContract(models.Model):
    """
    Employee contract based on the visa, work permits
    allows to configure different Salary structure
    """
    _inherit = 'hr.contract'
    _description = 'Employee Contract'

    struct_id = fields.Many2one('hr.payroll.structure', string='Salary Structure')
    schedule_pay = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semi-annually', 'Semi-annually'),
        ('annually', 'Annually'),
        ('weekly', 'Weekly'),
        ('bi-weekly', 'Bi-weekly'),
        ('bi-monthly', 'Bi-monthly'),
    ], string='Scheduled Pay', index=True, default='monthly',
    help="Defines the frequency of the wage payment.")
    resource_calendar_id = fields.Many2one(required=True, help="Employee's working schedule.")
    hra = fields.Monetary(string='HRA', help="House rent allowance.")
    travel_allowance = fields.Monetary(string="Travel Allowance", help="Travel allowance")
    da = fields.Monetary(string="DA", help="Dearness allowance")
    meal_allowance = fields.Monetary(string="Meal Allowance", help="Meal allowance")
    medical_allowance = fields.Monetary(string="Medical Allowance", help="Medical allowance")
    other_allowance = fields.Monetary(string="Other Allowance", help="Other allowances")
    type_id = fields.Many2one('hr.contract.type', string="Employee Category",
                              required=True, help="Employee category",
                              default=lambda self: self.env['hr.contract.type'].search([], limit=1))

    def get_all_structures(self):
        """
        Retrieve all related payroll structures, including parent structures.

        This method collects the payroll structures (`struct_id`) linked to the current record(s).
        If any structures are found, it also fetches their parent structures recursively
        using `_get_parent_structure()` and returns a list of unique structure IDs.

        Returns:
            list[int]: A list of unique payroll structure IDs.
                       Returns an empty list if no structures are linked.
        """
        structures = self.mapped('struct_id')
        if not structures:
            return []
        # YTI TODO return browse records
        return list(set(structures._get_parent_structure().ids))

    def get_attribute(self, code, attribute):
        return self.env['hr.contract.advantage.template'].search([('code', '=', code)], limit=1)[attribute]

    def set_attribute_value(self, code, active):
        """
        Set or reset a contract's attribute value based on an advantage template.

        This method updates the given field (`code`) on each contract:
          - If `active` is True, it searches for an `hr.contract.advantage.template`
            with the given code and applies its `default_value` to the contract field.
          - If `active` is False, it resets the field to 0.0.

        Args:
            code (str): The technical field name (code) of the advantage to update.
            active (bool): Whether to set the default value (True) or reset to 0.0 (False).

        Returns:
            None
        """
        for contract in self:
            if active:
                value = self.env['hr.contract.advantage.template'].search(
                    [('code', '=', code)], limit=1
                ).default_value
                contract[code] = value
            else:
                contract[code] = 0.0


class HrContractAdvantageTemplate(models.Model):
    _name = 'hr.contract.advantage.template'
    _description = "Employee's Advantage on Contract"

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    lower_bound = fields.Float(
        'Lower Bound',
        help="Lower bound authorized by the employer for this advantage")
    upper_bound = fields.Float(
        'Upper Bound',
        help="Upper bound authorized by the employer for this advantage")
    default_value = fields.Float('Default value for this advantage')
