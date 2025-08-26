# -*- coding:utf-8 -*-
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ContributionRegisterReport(models.AbstractModel):
    """
        Abstract model to generate the Contribution Register Report in Payroll.
        It collects payslip lines linked with contribution registers within a given date range,
        and computes totals for reporting purposes.
    """
    _name = 'report.jm_hr_payroll.report_contribution_register'
    _description = 'Generate report for contribution registers in payroll within a date range.'

    def _get_payslip_lines(self, register_ids, date_from, date_to):
        """
            Fetch and group payslip lines by contribution register.

            Args:
                register_ids (list): List of contribution register IDs to include.
                date_from (date): Start date for payslips.
                date_to (date): End date for payslips.

            Returns:
                dict: Mapping of register_id to corresponding payslip lines.
        """
        result = {}
        # Raw SQL query to fetch payslip lines based on register and date range
        self.env.cr.execute("""
            SELECT pl.id from hr_payslip_line as pl
            LEFT JOIN hr_payslip AS hp on (pl.slip_id = hp.id)
            WHERE (hp.date_from >= %s) AND (hp.date_to <= %s)
            AND pl.register_id in %s
            AND hp.state = 'done'
            ORDER BY pl.slip_id, pl.sequence""",
            (date_from, date_to, tuple(register_ids)))
        line_ids = [x[0] for x in self.env.cr.fetchall()]
        for line in self.env['hr.payslip.line'].browse(line_ids):
            # Initialize dict key if not exists and append line
            result.setdefault(line.register_id.id, self.env['hr.payslip.line'])
            result[line.register_id.id] += line
        return result

    @api.model
    def _get_report_values(self, docids, data=None):
        """
            Prepare report values for rendering the contribution register report.

            Args:
                docids (list): Document IDs from the wizard (context).
                data (dict): Additional data such as date range from the wizard.

            Returns:
                dict: Data structure required by the report template.
        """
        if not data.get('form'):
            raise UserError(_("Form content is missing, this report cannot be printed."))

        register_ids = self.env.context.get('active_ids', [])
        contrib_registers = self.env['hr.contribution.register'].browse(register_ids)

        # Fetch date range from wizard or set defaults
        date_from = data['form'].get('date_from', fields.Date.today())
        date_to = data['form'].get(
            'date_to', str(datetime.now() +
                           relativedelta(months=+1, day=1, days=-1))[:10]
        )

        # Fetch payslip lines grouped by register
        lines_data = self._get_payslip_lines(register_ids, date_from, date_to)

        # Calculate total per register
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
