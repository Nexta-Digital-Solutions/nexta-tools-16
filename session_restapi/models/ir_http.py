# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request

class IrSessionIdHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        info = super().session_info()   
        info["session_id"] = request.session.sid
        user_id = self.env['res.users'].search([ ('id', '=', info['uid']) ])
        info['employee_id'] = user_id.employee_id.id if user_id.employee_id else None
        return info