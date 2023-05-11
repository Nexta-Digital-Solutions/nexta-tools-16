# -*- coding: utf-8 -*-
from collections import defaultdict
from odoo import models, fields, api,_, SUPERUSER_ID

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _create_payment_vals_from_batch(self, batch_result):
        res = super(AccountPaymentRegister,self)._create_payment_vals_from_batch(batch_result)
        if batch_result.get('lines') and batch_result.get('lines').date_maturity:
            date = batch_result.get('lines').date_maturity

            res['date'] = date

        return res


