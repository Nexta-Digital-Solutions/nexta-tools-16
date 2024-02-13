# -*- coding: utf-8 -*-
# (c) 2024 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a
{
    'name': "Extensión de merge_invoice",
    'summary': """Este módulo se usa para modificar el módulo account_invoice_merge para que al fusionar facturas no tendrá en cuenta el user_id""",
    'description': """Este módulo se usa para modificar el módulo account_invoice_merge para que al fusionar facturas no tendrá en cuenta el user_id.""",
    'author': "NextaDS",
    'website': "https://www.nextads.es",
    'category': 'Accounting',
    'version': '0.0.0.1',
    'license': "LGPL-3",
    'depends': [
        'account',
        'account_invoice_merge',

    ],

    'installable': True
}