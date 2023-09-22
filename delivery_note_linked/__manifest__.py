# -*- coding: utf-8 -*-
{
    'name': "Delivery notes",
    'summary': """This module add notes to the sale.order and purchase.order model linked to the stock.picking notes""",
    'description': """This module add notes to the sale.order and  purchase.order model linked to the stock.picking notes""",
    'author': "NextaDS",
    'website': "https://www.nextads.es",
    'category': '',
    'version': '16.0.0.1',
    'license': "LGPL-3",
    'depends': [
        'sale',
        'base',
        'stock',
        'purchase',
        'sale_stock'
    ],

    'data': [
        'views/sale_order_delivery_note.xml',
        'views/purchase_order_delivery_note.xml',
        'views/stock_picking_delivery_note.xml',

    ],

    'installable': True
}