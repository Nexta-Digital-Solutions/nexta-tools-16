# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def cancel_effects(self):
        account_move_ids = self.env['account.move']
        for account_line_id in self:
            if not account_line_id.journal_id or not account_line_id.journal_id.cancel_account_id:
                raise ValidationError(
                    _("Need insert cancel effect account in journal {}").format(
                        account_line_id.journal_id.display_name
                    )
                )

            journal_id = account_line_id.journal_id
            debit_account_id = journal_id.cancel_account_id
            credit_account_id = self.account_id
            partner_id = self.partner_id or self.move_id.partner_id

            account_move_id = self.env['account.move'].create({
                'move_type': 'entry',
                'journal_id': journal_id.id if journal_id else False,
                'line_ids': account_line_id.create_aml(journal_id, debit_account_id, credit_account_id),
                'partner_id': partner_id.id if partner_id else False,
            })
            account_move_id.action_post()
            account_move_ids |= account_move_id

        return self.open_account_moves(account_move_ids)

    def open_account_moves(self, account_move_ids=False):

        if account_move_ids:
            # Abre la primera factura asociada (puedes ajustar la lógica según tus necesidades)
            account_move_form_view = self.env.ref('account.view_move_form')
            account_move_tree_view = self.env.ref('account.view_move_tree')
            return {
                'name': _('Accounting entries'),
                'res_model': 'account.move',
                'type': 'ir.actions.act_window',
                'views': [(account_move_tree_view.id, 'tree'),(account_move_form_view.id, 'form')],
                'view_mode': 'tree,form',
                'domain': [('id', 'in', account_move_ids.ids)],
            }
        else:
            # Maneja el caso en que no hay facturas asociadas
            return {'type': 'ir.actions.act_window_close'}

    def create_aml(self, journal_id, debit_account_id, credit_account_id):

        def insert_dict_aml(journal_id, account_id, reverse=False):
            dict= {
                'currency_id': journal_id.company_id.currency_id.id if journal_id.company_id.currency_id else False,
                'account_id': account_id.id,
                'date_maturity': self.date_maturity,
                'name': self.name
            }
            if self.credit:
                dict.update({
                    'credit': 0,
                    'debit': self.credit,
                })

            if self.debit:
                dict.update({
                    'debit': 0,
                    'credit': self.debit,
                })

            if reverse:
                if self.credit:
                    dict.update({
                        'debit': 0,
                        'credit': self.credit,
                    })

                if self.debit:
                    dict.update({
                        'credit': 0,
                        'debit': self.debit,
                    })

            return (0,0, dict)

        account_move_lines = []
        account_move_lines.append(insert_dict_aml(journal_id, credit_account_id))
        account_move_lines.append(insert_dict_aml(journal_id, debit_account_id, reverse=True))
        return account_move_lines