# -*- coding: utf-8 -*-
{
    'name': "Formato fecha de factura",

    'summary': """
        En la vista de facturas, la fecha de vencimiento no muestra los dias restantes, sino la misma fecha DD/MM/AA.""",

    'description': """
         En la vista de facturas, la fecha de vencimiento no muestra los dias restantes, sino la misma fecha DD/MM/AA.
    """,

    'author': "NextaDS",
    'website': "https://nextads.es/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'account',
    'version': '0.0.3',

    # any module necessary for this one to work correctly
    'depends': [
        'account',
    ],

    # always loaded
    'data': ['views/view_invoice_tree_custom.xml',
    ],
}
