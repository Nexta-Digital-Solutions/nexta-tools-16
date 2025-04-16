# -*- coding: utf-8 -*-
# (c) 2024 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def _prepare_invoice(self):
        invoice_vals = super(PurchaseOrder, self)._prepare_invoice()

        picking_ids = self.env.context.get('active_ids', [])
        # partner_refs = self.picking_ids.filtered(lambda picking: picking.partner_ref != False).mapped('partner_ref')
        partner_refs = self.picking_ids.filtered(lambda picking: picking.id in picking_ids and picking.partner_ref).mapped('partner_ref')
        partner_reference = ', '.join(partner_refs)

        invoice_vals.update({'partner_ref': partner_reference})
        return invoice_vals

