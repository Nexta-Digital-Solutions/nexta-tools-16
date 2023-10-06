# -*- coding: utf-8 -*-

from odoo import models, fields, api

class AttendanceGeoip(models.Model):
    _inherit = "hr.attendance"
    
    lat_in = fields.Float( digits = (17,7), string = "Latitude")
    long_in = fields.Float( digits = (17,7), string = "Longitude")
    lat_out = fields.Float( digits = (17,7), string = "Latitude")
    long_out = fields.Float( digits = (17,7), string = "Longitude")

    def open_map_in(self):
        for record in self:
            lat_in = record.lat_in
            long_in = record.long_in

            if lat_in and long_in:
                url = f"https://www.google.com/maps?q={lat_in},{long_in}&hl=es"

                return {
                    'type': 'ir.actions.act_url',
                    'target': 'new',
                    'url': url
                }

            else:
                return False

    def open_map_out(self):
        for record in self:
            lat_out = record.lat_out
            long_out = record.long_out

            if lat_out and long_out:
                url = f"https://www.google.com/maps?q={lat_out},{long_out}&hl=es"

                return {
                    'type': 'ir.actions.act_url',
                    'target': 'new',
                    'url': url
                }
            else:
                return False