# -*- coding:utf-8 -*-

from odoo import api, models


class PayslipDetailsReport(models.AbstractModel):
    """
        Abstract Model for generating the Payslip Details Report.

        This report provides breakdowns of payslip lines grouped by
        salary rule categories and contribution registers, helping to
        analyze the structure of employee salary components in detail.
    """
    _name = 'report.jm_hr_payroll.report_payslip_details'
    _description = 'Payslip Details Report'

    def get_details_by_rule_category(self, payslip_lines):
        """
            Group payslip lines by their salary rule categories.

            This method retrieves all payslip lines, organizes them by rule
            category, and recursively includes parent categories to provide
            hierarchical salary breakdowns.

            Args:
                payslip_lines (recordset): hr.payslip.line records.

            Returns:
                dict: Mapping of payslip_id -> list of dicts containing
                      rule category breakdown and line details.
        """
        PayslipLine = self.env['hr.payslip.line']
        RuleCateg = self.env['hr.salary.rule.category']

        def get_recursive_parent(current_rule_category, rule_categories=None):
            """Recursively collect parent categories for hierarchy building."""
            if rule_categories:
                rule_categories = current_rule_category | rule_categories
            else:
                rule_categories = current_rule_category

            if current_rule_category.parent_id:
                return get_recursive_parent(current_rule_category.parent_id, rule_categories)
            else:
                return rule_categories

        res = {}
        result = {}

        if payslip_lines:
            # SQL query to fetch payslip line IDs and group by category
            self.env.cr.execute(
                """
                SELECT pl.id, pl.category_id, pl.slip_id
                FROM hr_payslip_line as pl
                LEFT JOIN hr_salary_rule_category AS rc on (pl.category_id = rc.id)
                WHERE pl.id in %s
                GROUP BY rc.parent_id, pl.sequence, pl.id, pl.category_id
                ORDER BY pl.sequence, rc.parent_id""",
                (tuple(payslip_lines.ids),)
            )

            # Group fetched lines by payslip and category
            for x in self.env.cr.fetchall():
                result.setdefault(x[2], {})
                result[x[2]].setdefault(x[1], [])
                result[x[2]][x[1]].append(x[0])

            # Build hierarchical salary rule breakdown
            for payslip_id, lines_dict in result.items():
                res.setdefault(payslip_id, [])
                for rule_categ_id, line_ids in lines_dict.items():
                    rule_categories = RuleCateg.browse(rule_categ_id)
                    lines = PayslipLine.browse(line_ids)
                    level = 0

                    # Add recursive parent categories with totals
                    for parent in get_recursive_parent(rule_categories):
                        res[payslip_id].append({
                            'rule_category': parent.name,
                            'name': parent.name,
                            'code': parent.code,
                            'level': level,
                            'total': sum(lines.mapped('total')),
                        })
                        level += 1

                    # Add individual line breakdown under category
                    for line in lines:
                        res[payslip_id].append({
                            'rule_category': line.name,
                            'name': line.name,
                            'code': line.code,
                            'total': line.total,
                            'level': level
                        })
        return res

    def get_lines_by_contribution_register(self, payslip_lines):
        """
            Group payslip lines by contribution registers.

            Args:
                payslip_lines (recordset): hr.payslip.line records.

            Returns:
                dict: Mapping of payslip_id -> list of dicts containing
                      contribution register details and line breakdowns.
        """
        result = {}
        res = {}

        # Group payslip lines by contribution register
        for line in payslip_lines.filtered('register_id'):
            result.setdefault(line.slip_id.id, {})
            result[line.slip_id.id].setdefault(line.register_id, line)
            result[line.slip_id.id][line.register_id] |= line

        # Build summary totals and detailed lines
        for payslip_id, lines_dict in result.items():
            res.setdefault(payslip_id, [])
            for register, lines in lines_dict.items():
                # Register total
                res[payslip_id].append({
                    'register_name': register.name,
                    'total': sum(lines.mapped('total')),
                })
                # Detailed line breakdown
                for line in lines:
                    res[payslip_id].append({
                        'name': line.name,
                        'code': line.code,
                        'quantity': line.quantity,
                        'amount': line.amount,
                        'total': line.total,
                    })
        return res

    @api.model
    def _get_report_values(self, docids, data=None):
        """
            Prepare report values for the Payslip Details QWeb report.

            Args:
                docids (list): List of hr.payslip record IDs.
                data (dict): Extra report input data, if any.

            Returns:
                dict: Context dictionary for QWeb rendering.
        """
        payslips = self.env['hr.payslip'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'hr.payslip',
            'docs': payslips,
            'data': data,
            # Group payslip details by salary rule categories
            'get_details_by_rule_category': self.get_details_by_rule_category(
                payslips.mapped('details_by_salary_rule_category')
                .filtered(lambda r: r.appears_on_payslip)
            ),
            # Group payslip details by contribution registers
            'get_lines_by_contribution_register': self.get_lines_by_contribution_register(
                payslips.mapped('line_ids').filtered(lambda r: r.appears_on_payslip)
            ),
        }
