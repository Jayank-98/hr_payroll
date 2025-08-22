# -*- coding:utf-8 -*-
from odoo import api, fields, models


class HrContract(models.Model):
    """
        Extension of Employee Contract model.
        Adds payroll structure, payment schedule, and allowance-related fields
        for better HR and payroll management.
    """
    _inherit = 'hr.contract'
    _description = 'Extended Employee Contract with Payroll & Allowances'

    # Salary structure linked with the employee contract
    struct_id = fields.Many2one('hr.payroll.structure', string='Salary Structure')

    # Payment frequency of the salary
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

    # Employee's working calendar (mandatory)
    resource_calendar_id = fields.Many2one(required=True, help="Employee's working schedule.")

    # Different allowances
    hra = fields.Monetary(string='HRA', help="House rent allowance.")
    travel_allowance = fields.Monetary(string="Travel Allowance", help="Travel allowance")
    da = fields.Monetary(string="DA", help="Dearness allowance")
    meal_allowance = fields.Monetary(string="Meal Allowance", help="Meal allowance")
    medical_allowance = fields.Monetary(string="Medical Allowance", help="Medical allowance")
    other_allowance = fields.Monetary(string="Other Allowance", help="Other allowances")

    # Employee category (contract type)
    type_id = fields.Many2one('hr.contract.type', string="Employee Category",
                              required=True, help="Employee category",
                              default=lambda self: self.env['hr.contract.type'].search([], limit=1))

    def get_all_structures(self):
        """
            Get all salary structures linked with the contract,
            including parent-child hierarchy, without duplicates.
            @return: List of structure IDs in hierarchical order.
        """
        structures = self.mapped('struct_id')
        if not structures:
            return []
        # Return unique parent-child structure ids
        return list(set(structures._get_parent_structure().ids))

    def get_attribute(self, code, attribute):
        """
            Fetch a specific attribute value for a contract advantage
            using its code.
            @param code: Advantage code.
            @param attribute: Field name to fetch from template.
            @return: Attribute value.
        """
        return self.env['hr.contract.advantage.template'].search(
            [('code', '=', code)], limit=1
        )[attribute]

    def set_attribute_value(self, code, active):
        """
        Enable or disable an advantage for a contract.
        If active, assigns the default value from template.
        If not, resets the value to 0.0.
        @param code: Advantage code.
        @param active: Boolean to activate/deactivate.
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
    """
    Template for employee contract advantages.
    Stores configurations like default value, bounds,
    and codes to be used in contracts.
    """
    _name = 'hr.contract.advantage.template'
    _description = "Contract Advantage Template (Allowance Configuration)"

    name = fields.Char('Name', required=True)
    code = fields.Char('Code', required=True)
    lower_bound = fields.Float(
        'Lower Bound',
        help="Lower bound authorized by the employer for this advantage"
    )
    upper_bound = fields.Float(
        'Upper Bound',
        help="Upper bound authorized by the employer for this advantage"
    )
    default_value = fields.Float('Default value for this advantage')
