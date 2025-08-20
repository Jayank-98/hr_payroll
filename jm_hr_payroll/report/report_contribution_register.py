# -*- coding:utf-8 -*-
from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ContributionRegisterReport(models.AbstractModel):
    """
        Abstract Model to generate the Contribution Register Payroll Report.

        This report provides detailed lines of payslip contributions for selected
        registers within a specified date range. It calculates and summarizes the
        total contributions made during the period.
    """
    _name = 'report.om_jm_hr_payroll.report_contribution_register'
    _description = 'Payroll Contribution Register Report'

    def _get_payslip_lines(self, register_ids, date_from, date_to):
        """
            Fetch all payslip lines for the given contribution
             registers within the date range.

            Args:
                register_ids (list): List of hr.contribution.register record IDs.
                date_from (date): Start date of the payslip period.
                date_to (date): End date of the payslip period.

            Returns:
                dict: A dictionary mapping register_id -> hr.payslip.line recordset.
        """
        result = {}

        # SQL query to get payslip line IDs based on date range and contribution registers
        self.env.cr.execute(
            """
            SELECT pl.id 
            FROM hr_payslip_line AS pl
            LEFT JOIN hr_payslip AS hp ON (pl.slip_id = hp.id)
            WHERE (hp.date_from >= %s) 
            AND (hp.date_to <= %s)
            AND pl.register_id IN %s
            AND hp.state = 'done'
            ORDER BY pl.slip_id, pl.sequence
            """,
            (date_from, date_to, tuple(register_ids))
        )

        # Fetch all line IDs
        line_ids = [x[0] for x in self.env.cr.fetchall()]

        # Browse payslip line records and group them by register_id
        for line in self.env['hr.payslip.line'].browse(line_ids):
            result.setdefault(line.register_id.id, self.env['hr.payslip.line'])
            result[line.register_id.id] += line
        return result

    @api.model
    def _get_report_values(self, docids, data=None):
        """
            Generate the data required by the Contribution Register report.

            Args:
                docids (list): List of active record IDs (hr.contribution.register).
                data (dict): Input data, expected to include 'form' with date filters.

            Returns:
                dict: Dictionary containing report data to render in QWeb template.
        """
        if not data.get('form'):
            raise UserError(_("Report cannot be printed — required form details are missing."))

        # Active contribution registers selected from context
        register_ids = self.env.context.get('active_ids', [])
        contrib_registers = self.env['hr.contribution.register'].browse(register_ids)

        # Date range for the report
        date_from = data['form'].get('date_from', fields.Date.today())
        date_to = data['form'].get(
            'date_to', str(
                datetime.now() + relativedelta(months=+1, day=1, days=-1)
            )[:10]
        )

        # Fetch all payslip lines for the given registers and date range
        lines_data = self._get_payslip_lines(register_ids, date_from, date_to)

        # Calculate total contribution per register
        lines_total = {}
        for register in contrib_registers:
            lines = lines_data.get(register.id)
            lines_total[register.id] = lines and sum(lines.mapped('total')) or 0.0
        return {
            'doc_ids': register_ids,
            'doc_model': 'hr.contribution.register',
            'docs': contrib_registers,
            'data': data,
            'lines_data': lines_data,
            'lines_total': lines_total
        }
