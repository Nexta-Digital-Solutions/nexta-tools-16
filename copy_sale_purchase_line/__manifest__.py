# -*- coding: utf-8 -*-


{
    'name': 'Copy Sale and Purchase Order Line',
    'version': '16.0.0.1',
    'category': 'Sales',
    'license': 'OPL-1',
    'summary': "Copiar línea de pedido de venta, copiar línea de pedido de compra, duplicar línea de pedido de venta, duplicar línea de pedido de compra.",
    'description': """
        
        Copiar línea de compra y venta en Odoo,
        Copiar línea de pedido de venta en Odoo,
        Copiar línea de pedido de compra en Odoo,
        Botón de copiar en línea de compra y venta en Odoo,
        Fácil de copiar línea de pedido de venta y de compra en Odoo,

    """,
    'author': 'NextaDS',
    'website': 'https://www.nextads.es',
    'depends': ['base', 'sale_management', 'purchase_stock'],
    'data': [
        'views/sale_purchase_view.xml'
    ],
    'demo': [],
    'test': [],
    'installable': True,
    'auto_install': False,
    "images": ['static/description/Banner.gif'],
}
