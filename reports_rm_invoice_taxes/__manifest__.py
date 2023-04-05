# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a
{
    'name': "Eliminar impuestos de facturas",

    'summary': """
        Este módulo elimina las lineas de los impuestos en los reports de facturas""",

    'description': """
        Este módulo añade modificaciones a los reports en las facturas
    """,

    'author': "NextaDS",
    'website': "http://www.nextads.es",
    'license': "LGPL-3",

    'category': 'Account',
    'version': '16.0.1',

    'depends': ['stock_picking_report_valued',
                'sale',
                'stock',
                ],

    'data': [
        'report/report_invoice_document_custom.xml',


    ],

}
