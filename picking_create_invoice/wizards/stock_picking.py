# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class StockImmediateTransfer(models.TransientModel):
    _inherit = 'stock.immediate.transfer'

    def process(self):
        res = super(StockImmediateTransfer, self).process()
        for pick_id in self.pick_ids:
            if bool(pick_id.purchase_id) and pick_id.picking_type_code in ['incoming','outgoing']:
                pick_id.purchase_id.action_create_invoice()
        return res