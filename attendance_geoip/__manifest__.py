# -*- coding: utf-8 -*-
{
    'name': "attendance_geoip",

    'summary': """
       Geoip en Attendance mode, crea los campos de longitud y latitud con el botón para visualizar la coordenada
       """,
    'description': """
        Geoip en Attendance mode, crea los campos de longitud y latitud con el botón para visualizar la coordenada
    """,
    'author': "NextaDS",
    'website': "https://www.nextads.es",
    'category': 'Uncategorized',
    'version': '16.0.0.3',
    'depends': ['base',
                'hr_attendance'
     ],
    'license': 'LGPL-3',
    'data': [
        'views/hr_attendance_tree.xml',
    ]
}
