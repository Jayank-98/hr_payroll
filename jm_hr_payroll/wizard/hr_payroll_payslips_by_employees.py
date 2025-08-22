# -*- coding: utf-8 -*-

from odoo import fields, models, _
from odoo.exceptions import UserError


class HrPayslipEmployees(models.TransientModel):
    """
        Wizard model used to generate payslips for the selected employees
        within a specific payslip batch run.
    """
    _name = 'hr.payslip.employees'
    _description = 'Wizard for Generating Employee Payslips in a Batch Run'

    # Many2many field to select multiple employees for payslip generation
    employee_ids = fields.Many2many(
        comodel_name='hr.employee',
        relation='hr_payslip_employee_rel',
        column1='payslip_id',
        column2='employee_id',
        string='Selected Employees'
    )

    def compute_sheet(self):
        """
            Generate payslips for the selected employees based on the chosen
            payslip run dates and compute their salary structures.
        """
        payslips = self.env['hr.payslip']
        [data] = self.read()

        # Get the active payslip run from context
        active_id = self.env.context.get('active_id')
        if active_id:
            [run_data] = self.env['hr.payslip.run'].browse(active_id).read(
                ['date_start', 'date_end', 'credit_note']
            )

        from_date = run_data.get('date_start')
        to_date = run_data.get('date_end')


        # Raise an error if no employees are selected
        if not data['employee_ids']:
            raise UserError(_("You must select employee(s) to generate payslip(s)."))

        # Iterate over selected employees and create payslips
        for employee in self.env['hr.employee'].browse(data['employee_ids']):
            slip_data = self.env['hr.payslip'].onchange_employee_id(
                from_date, to_date, employee.id, contract_id=False
            )

            # Prepare payslip values
            res = {
                'employee_id': employee.id,
                'name': slip_data['value'].get('name'),
                'struct_id': slip_data['value'].get('struct_id'),
                'contract_id': slip_data['value'].get('contract_id'),
                'payslip_run_id': active_id,
                'input_line_ids': [
                    (0, 0, x) for x in slip_data['value'].get('input_line_ids')
                ],
                'worked_days_line_ids': [
                    (0, 0, x) for x in slip_data['value'].get('worked_days_line_ids')
                ],
                'date_from': from_date,
                'date_to': to_date,
                'credit_note': run_data.get('credit_note'),
                'company_id': employee.company_id.id,
            }

            # Create payslip record for employee
            payslips += self.env['hr.payslip'].create(res)

        # Compute the generated payslips
        payslips.compute_sheet()

        # Close the wizard after completion
        return {'type': 'ir.actions.act_window_close'}
