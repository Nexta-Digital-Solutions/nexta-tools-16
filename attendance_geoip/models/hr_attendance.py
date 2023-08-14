# -*- coding: utf-8 -*-

from odoo import models, fields, api

class AttendanceGeoip(models.Model):
    _inherit = "hr.attendance"
    
    lat_in = fields.Float( digits = (17,7), string = "Latitude")
    long_in = fields.Float( digits = (17,7), string = "Longitude")
    lat_out = fields.Float( digits = (17,7), string = "Latitude")
    long_out = fields.Float( digits = (17,7), string = "Longitude")
    