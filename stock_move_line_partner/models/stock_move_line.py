# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'


    # onhand_quantity = fields.Float(string="Cantidad a mano", compute='_compute_onhand_quantity', store=True)
    product_uom_qty = fields.Float(related="move_id.product_uom_qty", string="Demanda", required=False, )
    picking_partner_id = fields.Many2one(related='picking_id.partner_id', string="Cliente", store=True, readonly=True)