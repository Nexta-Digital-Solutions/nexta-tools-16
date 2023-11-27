# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api, _


class AccountMove(models.Model):
    _inherit = "account.move"

    sale_note = fields.Text(related="sale_id.delivery_note_sale", required=False, readonly=False)
