# -*- coding: utf-8 -*-
# (c) 2024 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _get_invoice_key_cols(self):
        return [
            "partner_id",
            "move_type",
            "currency_id",
            "journal_id",
            "company_id",
            "partner_bank_id",
        ]



