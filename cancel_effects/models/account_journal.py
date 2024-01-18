# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    cancel_account_id = fields.Many2one(
        comodel_name='account.account', check_company=True, copy=False, ondelete='restrict',
        string='Cancel Account')

    cancel_effect = fields.Boolean(string="Cancel efffect",  )


    def open_cancel_effects(self):
        account_ids = self.get_payment_account()
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_account_moves_all')
        action['domain'] = [
            ('display_type', 'not in', ('line_section', 'line_note')),
            ('parent_state', '!=', 'cancel'),
            ('journal_id', '=', self.id),
            ('reconciled', '=', False),
            ('account_id','in',account_ids.ids)
            ]
        action['context'] = "{'journal_type':'general'}"
        return action


    def get_payment_account(self):
        account_ids = self.inbound_payment_method_line_ids.mapped('payment_account_id')
        return account_ids