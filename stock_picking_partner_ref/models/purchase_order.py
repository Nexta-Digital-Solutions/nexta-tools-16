# -*- coding: utf-8 -*-
# (c) 2024 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.model
    def _prepare_invoice(self):
        invoice_vals = super(PurchaseOrder, self)._prepare_invoice()

        partner_refs = self.picking_ids.mapped('partner_ref')
        for ref in partner_refs:
            if ref == False:
                invoice_vals.update({'partner_ref': ''})
            else:
                partner_reference = ', '.join(partner_refs)
                invoice_vals.update({'partner_ref': partner_reference})
        return invoice_vals
