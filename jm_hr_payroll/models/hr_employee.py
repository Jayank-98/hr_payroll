# -*- coding:utf-8 -*-

from odoo import api, fields, models


class HrEmployee(models.Model):
    """
        Extension of HR Employee model to track related payslips.
        Provides a computed count of all payslips linked with the employee.
    """
    _inherit = 'hr.employee'
    _description = 'Extended Employee model for Payroll integration'

    # One2many field linking employee with all payslips
    slip_ids = fields.One2many(
        'hr.payslip', 'employee_id',
        string='Payslips', readonly=True
    )

    # Computed field showing total payslip count for the employee
    payslip_count = fields.Integer(
        compute='_compute_payslip_count',
        string='Payslip Count',
        groups="om_jm_hr_payroll.jm_hr_payroll_group_officer"
    )

    def _compute_payslip_count(self):
        """
            Compute the total number of payslips linked to each employee.
        """
        for employee in self:
            employee.payslip_count = len(employee.slip_ids)
