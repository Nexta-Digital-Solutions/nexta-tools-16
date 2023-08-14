# -*- coding: utf-8 -*-
{
    'name': "attendance_geoip",

    'summary': """
       Geoip en Attendance model""",
    'description': """
        Geoip en Attendance mode
    """,
    'author': "NextaDS",
    'website': "https://www.nextads.es",
    'category': 'Uncategorized',
    'version': '16.0.0.2',
    'depends': ['base',
                'hr_attendance'
     ],
    'license': 'LGPL-3',
    'data': [
        'views/hr_attendance_tree.xml',
    ]
}
