# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, _, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _commercial_fields(self):
        res =  super()._commercial_fields()
        if 'property_product_pricelist' in res:
            res.remove('property_product_pricelist')
        return res
