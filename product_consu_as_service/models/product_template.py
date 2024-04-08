# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.constrains('service_to_purchase', 'seller_ids', 'type')
    def _check_service_to_purchase(self):
        for template in self:
            if template.service_to_purchase:
                if template.type == 'product':
                    raise ValidationError(_("Product that is not a service can not create RFQ."))
                template._check_vendor_for_service_to_purchase(template.seller_ids)

    @api.onchange('type', 'expense_policy')
    def _onchange_service_to_purchase(self):
        products_template = self.filtered(lambda p: p.type == 'product' or p.expense_policy != 'no')
        products_template.service_to_purchase = False
