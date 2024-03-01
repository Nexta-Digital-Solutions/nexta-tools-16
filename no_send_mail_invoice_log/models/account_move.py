# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, exceptions, fields, models


class AccountMove(models.AbstractModel):
    _inherit = 'account.move'

    @api.model_create_multi
    def create(self, vals_list):
        res = super(AccountMove, self.with_context(mail_create_nolog=True)).create(vals_list)
        return res
