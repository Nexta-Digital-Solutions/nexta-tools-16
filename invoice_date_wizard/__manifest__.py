# -*- coding: utf-8 -*-
{
    'name': "Invoice date wizard",
    'summary': """This module add new field for set invoice date in create invoice wizard from sale order""",
    'description': """This module add new field for set invoice date in create invoice wizard from sale order""",
    'author': "NextaDS",
    'website': "https://www.nextads.es",
    'category': 'Uncategorized',
    'version': '15.0.0.1',
    'license': "LGPL-3",
    'depends': [
        'sale',
        'account'
    ],

    'data': [
        'wizards/sale_advance_payment_inv_views.xml',
    ],

    'installable': True
}