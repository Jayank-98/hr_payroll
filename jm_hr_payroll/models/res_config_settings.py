# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """
    Extends Odoo's system configuration settings to include payroll-related options.
    Allows enabling payroll accounting integration by activating the related module.
    """
    _inherit = 'res.config.settings'

    module_jm_hr_payroll_account = fields.Boolean(
        string='Payroll Accounting',
        help="Enable this option to install and configure the Payroll Accounting module."
    )


