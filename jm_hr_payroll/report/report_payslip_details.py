# -*- coding:utf-8 -*-

from odoo import api, models


class PayslipDetailsReport(models.AbstractModel):
    """
        Abstract model used to generate detailed payslip reports.
        Provides breakdown of salary lines by rule categories
        and contribution registers for reporting purposes.
    """
    _name = 'report.jm_hr_payroll.report_payslip_details'
    _description = ('Generate detailed payslip report grouped by'
                    ' rule categories and contribution registers.')

    def get_details_by_rule_category(self, payslip_lines):
        """
            Get payslip line details grouped by salary rule categories.

            Args:
                payslip_lines (recordset): hr.payslip.line records to process.

            Returns:
                dict: Mapping of payslip_id to a list of salary rule categories
                      and their corresponding payslip line details.
        """
        PayslipLine = self.env['hr.payslip.line']
        RuleCateg = self.env['hr.salary.rule.category']

        # Recursive function to get parent rule categories
        def get_recursive_parent(current_rule_category, rule_categories=None):
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
            # SQL fetch for payslip lines grouped by rule categories
            self.env.cr.execute("""
                SELECT pl.id, pl.category_id, pl.slip_id FROM hr_payslip_line as pl
                LEFT JOIN hr_salary_rule_category AS rc on (pl.category_id = rc.id)
                WHERE pl.id in %s
                GROUP BY rc.parent_id, pl.sequence, pl.id, pl.category_id
                ORDER BY pl.sequence, rc.parent_id""",
                (tuple(payslip_lines.ids),))

            # Organize fetched data into dictionary structure
            for x in self.env.cr.fetchall():
                result.setdefault(x[2], {})
                result[x[2]].setdefault(x[1], [])
                result[x[2]][x[1]].append(x[0])

            # Process grouped lines and compute totals
            for payslip_id, lines_dict in result.items():
                res.setdefault(payslip_id, [])
                for rule_categ_id, line_ids in lines_dict.items():
                    rule_categories = RuleCateg.browse(rule_categ_id)
                    lines = PayslipLine.browse(line_ids)
                    level = 0
                    # Add hierarchy of categories
                    for parent in get_recursive_parent(rule_categories):
                        res[payslip_id].append({
                            'rule_category': parent.name,
                            'name': parent.name,
                            'code': parent.code,
                            'level': level,
                            'total': sum(lines.mapped('total')),
                        })
                        level += 1
                    # Add individual payslip lines
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
        Get payslip line details grouped by contribution registers.

        Args:
            payslip_lines (recordset): hr.payslip.line records to process.

        Returns:
            dict: Mapping of payslip_id to contribution register details
                  and their corresponding payslip lines.
        """
        result = {}
        res = {}

        # Group lines by contribution register
        for line in payslip_lines.filtered('register_id'):
            result.setdefault(line.slip_id.id, {})
            result[line.slip_id.id].setdefault(line.register_id, line)
            result[line.slip_id.id][line.register_id] |= line

        # Prepare structured response
        for payslip_id, lines_dict in result.items():
            res.setdefault(payslip_id, [])
            for register, lines in lines_dict.items():
                # Add register summary
                res[payslip_id].append({
                    'register_name': register.name,
                    'total': sum(lines.mapped('total')),
                })
                # Add individual line details
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
        Prepare report values for rendering the detailed payslip report.

        Args:
            docids (list): List of hr.payslip IDs to include.
            data (dict): Additional data from the wizard.

        Returns:
            dict: Data structure required by the payslip details report template.
        """
        payslips = self.env['hr.payslip'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'hr.payslip',
            'docs': payslips,
            'data': data,
            # Method bindings for use in QWeb templates
            'get_details_by_rule_category':
                self.get_details_by_rule_category(
                    payslips.mapped(
                        'details_by_salary_rule_category'
                    ).filtered(lambda r: r.appears_on_payslip)),
            'get_lines_by_contribution_register':
                self.get_lines_by_contribution_register(
                    payslips.mapped('line_ids').filtered
                    (lambda r: r.appears_on_payslip)),
        }
