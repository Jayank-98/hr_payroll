# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil import relativedelta
from odoo import api, fields, models


class PayslipLinesContributionRegister(models.TransientModel):
    """
        Wizard for generating contribution register reports
        based on payslip lines within a selected date range.
    """
    _name = 'payslip.lines.contribution.register'
    _description = 'Wizard: Generate Contribution Register Report by Payslip Lines'

    # Report start date (defaults to first day of current month)
    date_from = fields.Date(string='Date From', required=True,
        default=datetime.now().strftime('%Y-%m-01'))

    # Report end date (defaults to last day of current month)
    date_to = fields.Date(string='Date To', required=True,
        default=str(datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1))[:10])

    def print_report(self):
        """
            Trigger the Contribution Register report action
            for selected payslip contribution registers.
        """
        # Fetch active records from context (selected contribution registers)
        active_ids = self.env.context.get('active_ids', [])

        # Prepare data payload for report
        datas = {
             'ids': active_ids,
             'model': 'hr.contribution.register',
             'form': self.read()[0]
        }

        # Return report action for contribution register
        return self.env.ref(
            'om_jm_hr_payroll.action_contribution_register'
        ).report_action([], data=datas)
