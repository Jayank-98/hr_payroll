# -*- coding:utf-8 -*-

from odoo import api, fields, models


class LeaveType(models.Model):
    """
        Inherits the HR Leave Type model to introduce additional functionality.

        Purpose:
        - Adds a 'Code' field that can be used to uniquely identify and
          manage different types of leaves (e.g., SL for Sick Leave,
          CL for Casual Leave, etc.).
        - Helps HR departments classify leave types in a standardized way.
    """
    _inherit = 'hr.leave.type'

    # Unique short code for the leave type (e.g., "SL", "CL")
    code = fields.Char(string='Code')
