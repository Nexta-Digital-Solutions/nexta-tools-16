# -*- coding: utf-8 -*-

from odoo import models, fields, api

class AttendanceGeoip(models.Model):
    _inherit = "hr.attendance"
    
    lat = fields.Float( digits = (17,7), string = "Latitude")
    long = fields.Float( digits = (17,7), string = "Longitude")
    