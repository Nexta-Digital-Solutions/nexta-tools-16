# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api


class StockMove(models.Model):
    _inherit = 'stock.move'

    # onhand_quantity = fields.Float(string="Cantidad a mano", required=False, )

    onhand_quantity = fields.Float(string="Cantidad a mano", compute='_compute_onhand_quantity', store=True)

    @api.depends('product_id', 'onhand_quantity')
    def _compute_onhand_quantity(self):
        for move in self:
            if move.product_id:
                quant = self.env['stock.quant'].search([
                    ('product_id', '=', move.product_id.id),
                    ('location_id', '=', move.location_id.id),], limit=1)

                if quant.quantity < 0:
                    move.onhand_quantity = -quant.quantity
                else:
                    move.onhand_quantity = quant.quantity


            else:
                move.onhand_quantity = quant.quantity

    # @api.onchange('product_id')
    # @api.depends('product_id')
    # def _onchange_quantity(self):
    #     producto = self.id
    #     if self._origin:
    #         producto = self._origin.id
    #     quantity_quant = self.env['stock.quant'].search([('product_tmpl_id','=',producto)])
    #     if self.quantity:
    #         quantity_quant.onhand_quantity = self.quantity
    #     else:
    #         self.onhand_quantity = False
