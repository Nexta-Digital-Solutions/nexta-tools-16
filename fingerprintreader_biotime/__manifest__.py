# -*- coding: utf-8 -*-
{
    'name': "fingerprintreader_biotime",

    'summary': """
        Baja las fichadas del software Biotime al modulo de asistencias
    """,
    'description': """
        Long description of module's purpose
    """,

    'author': "NextaDS",
    'website': "https://www.nextads.es",
    'license': 'LGPL-3',
    'category': 'Asistencias',
    'version': '16.0.0.2',
    'depends': [
        'base',
        'hr_attendance',
        'rest_time'
    ],
    'data': [
        'views/hr_attendance_tree.xml',
        'data/cron_get_employee.xml',
        'data/systemparameter.xml'
    ]
}
