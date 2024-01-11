# -*- coding: utf-8 -*-
{
    'name': "Not Copy Parent Pricelist",
    'summary': """Este modulo elimina la opcion de que los conbtactos hijos hereren la tarifa del padre""",
    'description': """Este modulo elimina la opcion de que los conbtactos hijos hereren la tarifa del padre""",
    'author': "NextaDS",
    'website': "https://www.nextads.es",
    'category': 'Products',
    'version': '16.0.0.1',
    'license': "LGPL-3",
    'depends': ['base',
            'product',
    ],

    'data': [
        'views/view_partner_property_form_nds.xml',
    ],

    'installable': True
}