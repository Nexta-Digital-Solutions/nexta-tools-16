# -*- coding: utf-8 -*-
# (c) 2022 Nexta - Carlos Ros <cros@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api,_
from odoo.exceptions import UserError


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def write(self, vals):
        self.check_unique_reference_product(vals)
        res = super(ProductProduct, self).write(vals)
        return res

    @api.model
    def create(self, values):
        self.check_unique_reference_product(values)
        user = super(ProductProduct, self).create(values)
        return user

    def check_unique_reference_product(self, vals):
        if vals.get('default_code'):
            product_id = self.search([('default_code','=',vals.get('default_code'))])
            if bool(product_id):
                raise UserError(_('Error already exist one product  with this reference'))