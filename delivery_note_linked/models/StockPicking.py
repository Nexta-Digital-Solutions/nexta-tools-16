# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api, _


class StockPicking(models.Model):
    _inherit = "stock.picking"

    sale_note = fields.Text(related="sale_id.delivery_note_sale", required=False, readonly=False)

    purchase_note = fields.Text(related="purchase_id.delivery_note_purchase", readonly=False)

# @api.onchange('delivery_note_sale')
# def _onchange_delivery_note_sale(self):
#     for order in self:
#         if order.picking_ids:
#             for picking in order.picking_ids:
#                 picking.note = order.delivery_note_sale
# @api.onchange('delivery_note_sale')
# def _onchange_delivery_note_sale(self):
#     for order in self:
#         if order.picking_ids:
#             order.picking_ids.update({'note':  order.delivery_note})
