# -*- coding: utf-8 -*-
{
    'name': "Delivery notes",
    'summary': """Este módulo agrega notas al modelo de pedido de venta y pedido de compra vinculados a las notas de stock.
        Adicionalmente se añade en el report de ventas y albarán.""",
    'description': """Este módulo agrega notas al modelo de pedido de venta y pedido de compra vinculados a las notas de stock.
    Adicionalmente se añade en el report de ventas y albarán.""",
    'author': "NextaDS",
    'website': "https://www.nextads.es",
    'category': '',
    'version': '15.0.0.3',
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
        'report/report_delivery_document_note.xml',
        'report/report_saleorder_document_note.xml',

    ],

    'installable': True
}