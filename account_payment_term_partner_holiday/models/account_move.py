# Copyright 2021 Tecnativa - Víctor Martínez
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _recompute_payment_terms_lines(self):
        _self = self
        if self.partner_id:
            _self = self.with_context(move_partner_id=self.partner_id.id)
        return super(AccountMove, _self)._recompute_payment_terms_lines()

    @api.onchange("invoice_date_due")
    def _onchange_invoice_date_due_account_payment_term_partner_holiday(self):
        """Recompute the due date to the next available date according to
        the holiday periods set in the partner.

        It must only be re-calculated when a payment term is not set.
        This prevents the due date to be changed again and that another
        given number of days are added according to what is set on the
        payment term.
        """
        if (
            self.invoice_date_due
            and self.partner_id
            and not self.invoice_payment_term_id
        ):
            new_invoice_date_due = self.partner_id._get_valid_due_date(
                self.invoice_date_due
            )
            if new_invoice_date_due != self.invoice_date_due:
                self.invoice_date_due = new_invoice_date_due


    # ORIGINAL: el metodo original retorna directamente false, pero los modulos de riesgos agregan el return del act window informando
    # riesgo excedido (si es el caso) y permite cancelar o continuar haciendo el post, asi que aqui ya no se puede retornar False
    # def action_post(self):
    #     """Inject a context for getting the partner when computing payment term."""
    #     for move in self:
    #         super(
    #             AccountMove, self.with_context(move_partner_id=move.partner_id.id)
    #         ).action_post()
    #     return False


    # NUEVO: considera un posible return y lo devuelve, de esta manera si es el caso se muestra el popup de riesgo excedido
    # permitiendo cancelar o hacer el post efectivamente
    def action_post(self):
        """Inject a context for getting the partner when computing payment term."""
        ret = False
        for move in self:
            r = super(
                AccountMove, self.with_context(move_partner_id=move.partner_id.id)
            ).action_post()
            if not ret and r:
                ret = r
        return ret