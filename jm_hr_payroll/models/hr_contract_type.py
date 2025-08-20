# -*- coding:utf-8 -*-

from odoo import api, fields, models


class ContractType(models.Model):
    _name = 'hr.contract.type'
    _description = 'Contract Type'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True, help="Name of the contract")
    sequence = fields.Integer(help="Gives the sequence when displaying a list of Contract.", default=10)
