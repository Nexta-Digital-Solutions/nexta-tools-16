# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def mass_sale_confirm_action(self):
        sale_ids = self.browse(self._context.get('active_ids'))
        for sale in sale_ids:
            if sale.state in ['draft', 'sent']:
                sale.action_confirm()