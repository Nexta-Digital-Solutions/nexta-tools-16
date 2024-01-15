# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a
{
    'name': "Reports sin impuestos",

    'summary': """
        Este módulo elimina los impuestos en los reports de ventas y facturación""",

    'description': """
        Este módulo añade modificaciones a los reports:
            · Sale
            · Account
            
            
    """,

    'author': "NextaDS",
    'website': "http://www.nextads.es",
    'license': "LGPL-3",

    'category': '',
    'version': '0.0.0.2',

    'depends': ['sale',
                'account',
                'purchase',
                ],

    'data': [
        'report/report_saleorder_document_generic.xml',
        'report/report_invoice_document_generic.xml',
        'report/report_purchaseorder_document_generic.xml',


    ],

}
