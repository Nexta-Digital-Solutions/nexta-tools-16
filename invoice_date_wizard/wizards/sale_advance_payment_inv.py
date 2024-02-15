# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Carlos Ros <cros@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api, _


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'


    invoice_date = fields.Date(string="Invoice date", required=False, default=fields.Date.context_today)


    def create_invoices(self):

        res = super(SaleAdvancePaymentInv, self.with_context(
            invoice_date=self.invoice_date)).create_invoices()

        return res