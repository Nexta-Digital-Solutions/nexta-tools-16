# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api, _



class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    delivery_note_purchase = fields.Text(required=False, readonly=False)



#     @api.onchange('delivery_note')
#
#     def _onchange_delivery_note(self):
#         for order in self:
#             if order.picking_ids:
#                 order.picking_ids.write({'note':  order.delivery_note})
