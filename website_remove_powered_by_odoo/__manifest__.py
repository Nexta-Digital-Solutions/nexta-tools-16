# -*- coding: utf-8 -*-
# © 2024 Jbasiero - Nextads (www.nextads.es)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    'name': 'Website remove Powered by Odoo',
    'version': '16.0.0.0.1',
    'category': 'website',
    'depends': [
        'website',
        'web',
    ],
    'author': 'Nextads',
    'license': 'AGPL-3',
    'website': 'https://www.nextads.es',
    'sequence': 1,
    'data': [
        'views/website_remove_powered_by_odoo.xml',
    ],
    'installable': True,
    'application': False
}
