# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import _, api, exceptions, fields, models, tools, registry, SUPERUSER_ID, Command


class AccountMove(models.AbstractModel):
    _inherit = 'account.move'

    def _notify_classify_recipients(self, recipient_data, model_name, msg_vals=None):
        res = super(AccountMove, self)._notify_classify_recipients(recipient_data, model_name, msg_vals)
        if bool(self._name == 'account.move'):

            for item in res:
                #Quitar de la lista si es igual a user.
                if item.get('notification_group_name') == 'user':
                    res.remove(item)

        return res
