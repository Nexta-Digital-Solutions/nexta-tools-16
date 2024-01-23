# -*- coding: utf-8 -*-
{
    'name': "Crear factura de compra al validar albaran entrada",

    'summary': """
        Crear factura de compra al validar albaran entrada.""",

    'description': """
    Crear factura de compra al validar albaran entrada
    
    """,

    'author': "NextaDS",
    'website': "https://nextads.es/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'stock',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': [
        'stock',
        'purchase_stock',
    ],

    # always loaded
    'data': [
    ],
}
