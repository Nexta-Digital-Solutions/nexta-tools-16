# -*- coding: utf-8 -*-

from odoo import models, fields, api
import requests
import json
import logging
from odoo.exceptions import AccessError
from datetime import datetime, timedelta
import random
import pandas as pd

_logger = logging.getLogger(__name__)

class fingerprintreader_biotime(models.Model):
    _inherit = "hr.attendance"
    
    physical_reader = fields.Boolean( string = "Physical reader")
    
    KEY_LOGIN    = 'biotime_url_login'
    KEY_FICHADAS = 'biotime_url_fichadas'
    KEY_USERNAME = 'biotime_username'
    KEY_PASSWORD = 'biotime_password'
    KEY_LAST_START_TIME = 'biotime_last_start_time'
    
    def _cron_get_signings(self):
        lastDate = self.get_employees()
        self.saveLastSigning(lastDate)

        
    def api_login (self):
        headers = {
            "Content-Type": "application/json"
        }
        biotime_url_login = self.env['ir.config_parameter'].get_param(self.KEY_LOGIN)
        biotime_username  = self.env['ir.config_parameter'].get_param(self.KEY_USERNAME)
        biotime_password  = self.env['ir.config_parameter'].get_param(self.KEY_PASSWORD)
        data = {
            "username": biotime_username,
            "password": biotime_password
        }
        try:
            response = requests.post(biotime_url_login, timeout = 5, data=json.dumps(data), headers=headers)
            token = response.json()['token']
            return token
        except requests.exceptions.ConnectionError as e:
            raise AccessError (e.args[0].reason.args[1])
            
        
    def get_signings(self, employee_barcode):
        biotime_url_fichadas = self.env['ir.config_parameter'].get_param(self.KEY_FICHADAS)
        biotime_last_start_time  = self.env['ir.config_parameter'].get_param(self.KEY_LAST_START_TIME) 
        biotime_last_start_time = biotime_last_start_time if biotime_last_start_time else '2022-01-01 00:00:00'
        biotime_url_fichadas += "?emp_code=%s" % (employee_barcode)
        biotime_url_fichadas += "&start_time=%s" % (biotime_last_start_time) 
        biotime_url_fichadas += "&page_size=9999"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Token %s" % self.api_login()
        }
        if (biotime_url_fichadas):
            response = requests.get(biotime_url_fichadas, headers = headers)
            response_data = response.json()
            data_signings = []
            for line in response_data['data']:
                record_id = line['id']
                record_employee_id = line['emp_code']
                record_employee_name = "%s %s" % (line['first_name'], line['last_name'])
                record_employee_signings = line['upload_time']
                #_logger.debug ("Fichada --> %s - %s - %s - %s" % (record_id, record_employee_id, record_employee_name, record_employee_signings))
                employee = {  
                            'id':   record_id, 
                            'name': record_employee_name, 
                            'date': record_employee_signings 
                }
                data_signings += [ employee ]
            return data_signings
    
    def get_employees(self):
        employees = self.env['hr.employee'].search( [ ('barcode', '!=', False) ], order = 'barcode')
        for employee in employees:
            total_seconds = 0
            data_signings = self.get_signings(employee.barcode)
          
            for idx, record in enumerate(data_signings):
                signings = datetime.strptime(record['date'], '%Y-%m-%d %H:%M:%S')
                if (idx == 0):
                    aux_signings = datetime.today()  
                
                _logger.debug ('### %s - %s ' % (employee.name, signings))
                
                if (aux_signings and aux_signings.date() != signings.date()):
                    time_start = signings
                    time_end   = time_start + timedelta (seconds = 28800) + timedelta(seconds = random.uniform(60,1200))
                    total_seconds = (time_end - time_start).total_seconds() 
                    seconds = total_seconds 
                    worked_hours = timedelta(seconds = seconds)
                                                
                    self.setAttendance(employee, signings,time_end, worked_hours)
                    aux_signings = signings
                    
        return signings
                            
    def setAttendance (self, employee, check_in, check_out, worked_hours):
        m, s = divmod(worked_hours.total_seconds(), 60)
        h, m = divmod(m, 60)
        self.create ({
            'employee_id': employee.id,
            'check_in': check_in,
            'check_out': check_out,
            'worked_hours': h + m + s,
            'physical_reader': True
        })
        _logger.debug ('Grabando ### %s - %s - %s - %s' % (employee.name, check_in, check_out, worked_hours))
        
    def saveLastSigning(self, lastDate):
        self.env['ir.config_parameter'].set_param(self.KEY_LAST_START_TIME, lastDate)