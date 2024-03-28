# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ResPartner(models.Model):
    _inherit = 'res.partner'

    requested_amount = fields.Float(string="Importe solicitado")
    risk_group = fields.Integer(string="Grupo de riesgo:")