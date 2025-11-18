# -*- coding: utf-8 -*-
# (c) 2025 Nexta - Carlos Ros <cros@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

{
    "name": "Comunicación VERI*FACTU OCA NDS",
    "version": "16.0.1.1.0",
    'summary': """Este modulo es para cuando falla y no muestra el qr en la factura como pasaba en grader""",
    'description': """Este modulo es para cuando falla y no muestra el qr en la factura como pasaba en grader""",
    "category": "Accounting/Localizations/EDI",
    "website": "https://github.com/OCA/l10n-spain",
    "author": "Aures Tic,ForgeFlow,Tecnativa,Factor Libre,Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "installable": True,
    "depends": ["l10n_es_verifactu_oca"],
    "data": [
        "views/report_invoice.xml",
    ],
}
