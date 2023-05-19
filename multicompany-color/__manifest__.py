# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a
{
    'name': "Multicompany color",

    'summary': """
        Este módulo añade diferentes colores de la barra de navegación de odoo, que cambia en función de la empresa que esté activa""",

    'description': """
        Este módulo añade diferentes colores de la barra de navegación de odoo, que cambia en función de la empresa que esté activa""",

    'author': "NextaDS",
    'website': "http://www.nextads.es",
    'license': "LGPL-3",

    'category': '',
    'version': '16.0.1',

    'depends': ['base',
                'web'
                ],

    'data': [
        'views/layout_multicompany_color.xml',
    ],
}
