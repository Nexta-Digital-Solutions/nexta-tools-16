# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api, _


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    partner_ref = fields.Char(string="Albarán de proveedor", required=False,)
    picking_partner = fields.Many2one(comodel_name="stock.move", string="Cliente", required=False,)

