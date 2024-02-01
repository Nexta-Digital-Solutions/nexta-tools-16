# -*- coding: utf-8 -*-
{
    'name': "Mass Sale Confirm",

    'summary': """
        Este modulo añade una accion para poder validar/confirmar presupuestos de venta masivamente""",

    'description': """
    Este modulo añade una accion para poder validar/confirmar presupuestos de venta masivamente
    """,

    'author': "NextaDS",
    'website': "https://nextads.es/",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/14.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Sale',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': [
        'sale',
    ],

    # always loaded
    'data': [
        'views/sale_order_views.xml'
    ],

}
