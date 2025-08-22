# -*- coding: utf-8 -*-
{
    'name': 'Odoo 17 HR Payroll Management',
    'category': 'Human Resources/Payroll',
    'version': '17.0.1.0.4',
    'sequence': 1,
    'author': 'Jayank M Aghara',
    'summary': 'Comprehensive Payroll Management for Odoo 17 Community Edition',
    'description': """
Odoo 17 HR Payroll Management
=============================

A complete payroll solution for Odoo 17 Community Edition.  
This module helps HR managers and accountants to manage employee payroll processes efficiently.  

Key Features:
--------------
✔ Employee contract management with salary structures  
✔ Salary rules and categories with flexible configurations  
✔ Automatic payslip generation (individual and batch)  
✔ Integration with leaves (paid/unpaid) and contracts  
✔ Payroll reports: Payslip, Contribution Register, Detailed Payslip  
✔ Contract history tracking  
✔ Predefined mail templates for payroll communication  

Ideal for organizations looking to simplify and automate salary computation and reporting in Odoo 17 Community.
""",
    'website': 'https://github.com/Jayank-98/hr_payroll/tree/17.0',
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
