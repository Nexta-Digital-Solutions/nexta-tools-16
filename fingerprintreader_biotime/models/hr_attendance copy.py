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
        self.updateHours()
        
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
        hours_workday = timedelta(days=0, seconds=0, microseconds=0, milliseconds=0, minutes=0, hours=8, weeks=0)
        for employee in employees:
            aux_signings_date = datetime.today()
            if cont % 2 > 0: 
                self.InsertAttendance(aux_employee, total_seconds,total_seconds_day,aux_signings_date,signings_date,worked_hours)
            
            total_seconds_day = total_seconds = 0
            cont = 0
            aux_employee = employee
            attendance_insert = False
            for idx, record in enumerate(data_signings):
                signings_date = datetime.strptime(record['date'], '%Y-%m-%d %H:%M:%S')
                _logger.debug ('### %s - %s ' % (employee.name, signings_date))
                cont += 1
                if (idx == 0):
                    aux_signings_date = signings_date  
                elif ( aux_signings_date.date() == signings_date.date() and cont % 2 == 0 ):
                    time_start = aux_signings_date
                    time_end   = signings_date
                    total_seconds = round((time_end - time_start).total_seconds())
                    total_seconds_day += total_seconds
                    attendance_insert = True
                    
                if (attendance_insert):
                    if (aux_signings_date.date() == signings_date.date()):
                        hours = total_seconds * 60 * 60
                        worked_hours = timedelta(hours=hours)
                        if (total_seconds_day > 28800):
                            diferencia = total_seconds - 28800
                            worked_hours = - timedelta( hours = abs(diferencia)) + timedelta(minutes = random.uniform(1,20))
                        self.setAttendance(employee, aux_signings_date, signings_date, worked_hours)
                   
                    attendance_insert = False
    
                aux_signings_date = signings_date     
    def InsertAttendance (self, employee, total_seconds, total_seconds_day, aux_signings_date,signings_date, worked_hours):
        if (aux_signings_date.date() == signings_date.date()):
                        hours = total_seconds * 60 * 60
                        worked_hours = timedelta(hours=hours)
                        if (total_seconds_day > 28800):
                            diferencia = total_seconds - 28800
                            worked_hours = - timedelta( hours = abs(diferencia)) + timedelta(minutes = random.uniform(1,20))
                        self.setAttendance(employee, aux_signings_date, signings_date, worked_hours)
                        
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
        
    def saveLastSigning(self, lastDate):
        self.env['ir.config_parameter'].set_param(self.KEY_LAST_START_TIME, lastDate)
        
    def updateHours (self):
        systemdate = datetime.fromisoformat(datetime.today().isoformat()).replace(second=0, minute=0, hour=0)
        records = self.search([('create_date', '>=', str(systemdate)), ('worked_hours', '>', '8.30')], order = 'employee_id')
        for assistence in records:
            horas = assistence.worked_hours
            diferencia = 8 - horas
            fecha = assistence.check_out - timedelta( hours = abs(diferencia)) + timedelta(minutes = random.uniform(1,20))
            assistence.update ({
                'check_out': fecha
            })