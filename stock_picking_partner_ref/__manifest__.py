# -*- coding: utf-8 -*-
# (c) 2024 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a
{
    'name': "Referencia proveedor de compras",
    'summary': """En las facturas, modelo account.move, se crea un campo referencia de albarán de proveedor que tiene su valor del stock.picking.
    y al fusionar facturas conservará la concatenación de las 3 referencias de proveedor.
    Permite filtrar por la referencia del proveedor tanto en la compra como en el albarán.""",
    'description': """En las facturas, modelo account.move, se crea un campo referencia de albarán de proveedor que tiene su valor del stock.picking
    y al fusionar facturas conservará la concatenación de las 3 referencias de proveedor.
    Permite filtrar por la referencia del proveedor tanto en la compra como en el albarán.""",
    'author': "NextaDS",
    'website': "https://www.nextads.es",
    'category': 'Stock',
    'version': '16.0.0.7',
    'license': "LGPL-3",
    'depends': [
        'purchase',
        'stock',
        'stock_picking_invoice_link',
        'account',
        'purchase_stock_picking_invoice_link',
        # 'picking_create_invoice',
        'account_invoice_merge',

    ],

    'data': [
        'views/view_picking_internal_search_nds.xml',
        'views/view_purchase_order_filter_nds.xml',
        'views/view_picking_form_nds.xml',
        'views/view_move_form_nds.xml',
        'views/vpicktree_nds.xml',
        'views/view_invoice_tree_nds.xml',
    ],

    'installable': True
}