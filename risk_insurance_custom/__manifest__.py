# -*- coding: utf-8 -*-
# (c) 2023 Nexta - Guillermo Fernandez <gfernandez@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a
{
    "name": "Risk Insurance Custom",
    "summary": "Añadir campos de Importe solicitado y Grupo de Riesgo en Seguro de riesgo del modelo res.partner",
    "version": "15.0.1.1.0",
    "category": "Res partner",
    "license": "AGPL-3",
    'author': "NextaDS",
    'website': "https://www.nextads.es",
    "depends": ["base", "partner_risk_insurance"],
    "data": [
        "views/risk_insurance_custom.xml",
    ],
    "installable": True,
}
