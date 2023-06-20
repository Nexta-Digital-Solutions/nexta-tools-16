# -*- coding: utf-8 -*-
# (c) 2022 Nexta - Carlos Ros <cros@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_purchase_order_line_from_procurement(self, product_id, product_qty, product_uom, company_id, values, po):
        res = super(PurchaseOrder, self)._prepare_purchase_order_line_from_procurement(product_id, product_qty,
                                                                                       product_uom, company_id, values,
                                                                                       po)
        orderpoint_id = values.get('orderpoint_id')
        if bool(orderpoint_id) and self._context.get('origins'):
            origin = self._context.get('origins')[orderpoint_id.id]
            if bool(origin):
                sale_id = self.env['sale.order'].search([('name', '=', origin)])
                if bool(sale_id):
                    sale_line_id = sale_id.order_line.filtered(lambda x: x.product_id.id == product_id.id)
                    if bool(sale_line_id):
                        res['sale_line_id'] = sale_line_id.id
        return res
