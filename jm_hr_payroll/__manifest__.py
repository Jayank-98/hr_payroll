# -*- coding:utf-8 -*-

{
    'name': 'HR Payroll Management - Odoo 16 Community',
    'category': 'Human Resources/Payroll',
    'version': '16.0.1.0.1',
    'sequence': 101,
    'author': 'Jayank M Aghara',
    'summary': 'Comprehensive Payroll Management for Odoo 16 Community Edition',
    'description': """
HR Payroll Management - Odoo 16 Community
=========================================

This module provides a complete payroll management system for Odoo 16 Community Edition.  
It enables HR departments to efficiently manage:
- Employee contracts and salary structures  
- Salary rules and computation  
- Leave and absence integration  
- Payslip generation and reporting  
- Payroll reporting and contribution register  

Designed for seamless integration with Odoo’s HR and Accounting modules, this solution simplifies payroll operations while ensuring compliance and accuracy.
    """,
    'license': 'LGPL-3',
    'depends': [
        'mail',
        'hr_contract',
        'hr_holidays',
    ],
    'data': [
        'security/hr_payroll_security.xml',
        'security/ir.model.access.csv',
        'data/hr_payroll_sequence.xml',
        'data/hr_payroll_category.xml',
        'data/hr_payroll_data.xml',
        'wizard/hr_payroll_payslips_by_employees_views.xml',
        'views/hr_contract_type_views.xml',
        'views/hr_contract_views.xml',
        'views/hr_salary_rule_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_employee_views.xml',
        'views/hr_payroll_report.xml',
        'wizard/hr_payroll_contribution_register_report_views.xml',
        'views/res_config_settings_views.xml',
        'views/report_contribution_register_templates.xml',
        'views/report_payslip_templates.xml',
        'views/report_payslip_details_templates.xml',
        'views/hr_contract_history_views.xml',
        'views/hr_leave_type_view.xml',
        'data/mail_template.xml',
    ],
    'images': ['static/description/banner.png'],
    'application': True,
}
