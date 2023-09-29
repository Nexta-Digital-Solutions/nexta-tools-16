# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a
{
    'name': "Formatos para reports",

    'summary': """
        Este módulo añade modificaciones personalizadas en todos los reports
            · Albarán valorado
            · Albarán sin valorar""",

    'description': """
        Este módulo añade modificaciones a los siguientes reports:
            · Albarán valorado
            · Albarán sin valorar
            
    """,

    'author': "NextaDS",
    'website': "http://www.nextads.es",
    'license': "LGPL-3",

    'category': 'Stock',
    'version': '16.2.5',

    'depends': ['sale_management',
                'sale',
                'stock',
                ],

    'data': [
        # 'report/report_stock_picking_address.xml',
        'report/report_albaran_sin_valorar.xml',
        'report/paperformat_albaran_report.xml',
        # 'report/stock_report_delivery_has_serial_move_line_descripcion.xml',

    ],
    'css': [
        'static/src/css/report_style.css',
    ],

}
