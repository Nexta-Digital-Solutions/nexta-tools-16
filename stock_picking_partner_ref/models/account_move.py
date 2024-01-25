# -*- coding: utf-8 -*-
# (c) 2024 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    partner_ref = fields.Char(string="Albarán de proveedor", required=False, compute="_compute_partner_ref")
    partner_reference = fields.Char(string="Albarán de proveedor", required=False)

    @api.depends('picking_ids.partner_ref')
    def _compute_partner_ref(self):
        for record in self:
            if record.picking_ids and any(picking.partner_ref for picking in record.picking_ids):
                partner_refs = [picking.partner_ref for picking in record.picking_ids if picking.partner_ref]
                record.partner_ref = ', '.join(partner_refs) if partner_refs else False
            else:
                record.partner_ref = False
    # def _get_invoice_key_cols(self):
    #     res = super(AccountMove, self)._get_invoice_key_cols(self)
    #     res = "partner_ref"
    #
    #     return res
