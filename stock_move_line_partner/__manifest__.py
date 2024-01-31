# Copyright 2021 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
{
    "name": "Movimientos de albaranes",
    'summary': """ Añade al modelo stock.move.line los campos para las cantidades y el cliente""",
    'description': """
   Añade al modelo stock.move.line(vista lista) los campos para el cliente y las cantidades:
        · product_id
        · product_uom_qty
        · quantity_done
        · quantity
""",

    "version": "0.0.4",
    "license": "LGPL-3",
    "website": "",
    "author": "NextaDS",
    "category": "Stock",
    "depends": ["stock",],
    'data': [
        'views/view_move_tree_nds.xml',
        'views/stock_move_line_view_search_nds.xml',
        'views/view_move_line_tree_nds.xml',
        'views/action_stock_move_line.xml',
    ],
    "installable": True,
}
