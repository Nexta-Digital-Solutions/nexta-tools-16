# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api, _


class SaleNote(models.Model):
    _inherit = "sale.order"

    delivery_note_sale = fields.Text(required=False, readonly=False)
