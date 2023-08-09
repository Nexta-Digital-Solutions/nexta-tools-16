# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request

class IrSessionIdHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()
        #info["user_id"] = request.session.uid,
        info["session_id"] = request.session.sid
        return info