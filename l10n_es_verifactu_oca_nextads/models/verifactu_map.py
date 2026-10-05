# Copyright 2024 Aures TIC - Almudena de La Puente <almudena@aurestic.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import _, api, exceptions, fields, models


class AeatVerifactuMap(models.Model):
    _name = "verifactu.map"
    _description = "VERI*FACTU mapping"

    name = fields.Char(string="Model", required=True)
    date_from = fields.Date()
    date_to = fields.Date()
    map_lines = fields.One2many(
        comodel_name="verifactu.map.line",
        inverse_name="verifactu_map_id",
        string="Lines",
    )

    @api.constrains("date_from", "date_to")
    def _unique_date_range(self):
        for record in self:
            record._unique_date_range_one()

    def _unique_date_range_one(self):
        # Based in l10n_es_aeat module
        domain = [("id", "!=", self.id)]
        if self.date_from and self.date_to:
            domain += [
                "|",
                "&",
                ("date_from", "<=", self.date_to),
                ("date_from", ">=", self.date_from),
                "|",
                "&",
                ("date_to", "<=", self.date_to),
                ("date_to", ">=", self.date_from),
                "|",
                "&",
                ("date_from", "=", False),
                ("date_to", ">=", self.date_from),
                "|",
                "&",
                ("date_to", "=", False),
                ("date_from", "<=", self.date_to),
            ]
        elif self.date_from:
            domain += [("date_to", ">=", self.date_from)]
        elif self.date_to:
            domain += [("date_from", "<=", self.date_to)]
        date_lst = self.search(domain)
        if date_lst:
            raise exceptions.UserError(
                _("Error! The dates of the record overlap with an existing " "record.")
            )



MAP_LINE_TAXES = {
    "verifactu_map_line_S1": [
        "account_tax_template_s_iva21b",
        "account_tax_template_s_iva0b",
        "account_tax_template_s_iva2b",
        "account_tax_template_s_iva4b",
        "account_tax_template_s_iva5b",
        "account_tax_template_s_iva7-5b",
        "account_tax_template_s_iva10b",
        "account_tax_template_s_iva21s",
        "account_tax_template_s_iva10s",
        "account_tax_template_s_iva0s",
        "account_tax_template_s_iva2s",
        "account_tax_template_s_iva4s",
        "account_tax_template_s_iva5s",
        "account_tax_template_s_iva7-5s",
        "account_tax_template_s_iva0",
    ],
    "verifactu_map_line_S2": [
        "account_tax_template_s_iva0_isp",
    ],
    "verifactu_map_line_N1": [
    ],
    "verifactu_map_line_N2": [
        "account_tax_template_s_iva_e",
        "account_tax_template_s_iva0_sp_i",
        "account_tax_template_s_iva_ns_b",
        "account_tax_template_s_iva_ns",
    ],
    "verifactu_map_line_RE": [
        "account_tax_template_s_req52",
        "account_tax_template_s_req014",
        "account_tax_template_s_req062",
        "account_tax_template_s_req1",
        "account_tax_template_s_req05",
        "account_tax_template_s_req026",
        "account_tax_template_s_req0",
    ],
    "verifactu_map_line_tax_not_included": [
        "account_tax_template_s_irpf1",
        "account_tax_template_s_irpf2",
        "account_tax_template_s_irpf7",
        "account_tax_template_s_irpf9",
        "account_tax_template_s_irpf15",
        "account_tax_template_s_irpf18",
        "account_tax_template_s_irpf19",
        "account_tax_template_s_irpf19a",
        "account_tax_template_s_irpf195a",
        "account_tax_template_s_irpf20",
        "account_tax_template_s_irpf20a",
        "account_tax_template_s_irpf21",
        "account_tax_template_s_irpf21a",
        "account_tax_template_s_irpf24",
    ],
    "verifactu_map_line_base_not_included": [
        "account_tax_template_s_iva0_ns",
    ],
    "verifactu_map_line_E2": [
        "account_tax_template_s_iva0_e",
    ],
    "verifactu_map_line_E5": [
        "account_tax_template_s_iva0_ic",
    ],
}


class AeatVerifactuMapLines(models.Model):
    _name = "verifactu.map.line"
    _description = "VERI*FACTU mapping line"

    code = fields.Char(required=True)
    name = fields.Char()
    taxes = fields.Many2many(comodel_name="account.tax.template")
    verifactu_map_id = fields.Many2one(
        comodel_name="verifactu.map", string="Parent mapping", ondelete="cascade"
    )

    @api.model
    def _load_l10n_es_taxes(self) -> None:
        """Link the l10n_es tax templates, skipping those that don't exist in the
        installed l10n_es version."""
        module = "l10n_es_verifactu_oca_nextads"
        for line_xmlid, tax_xmlids in MAP_LINE_TAXES.items():
            line = self.env.ref(f"{module}.{line_xmlid}", raise_if_not_found=False)
            if not line:
                continue
            taxes = self.env["account.tax.template"]
            for tax_xmlid in tax_xmlids:
                taxes |= self.env.ref(
                    f"l10n_es.{tax_xmlid}", raise_if_not_found=False
                ) or self.env["account.tax.template"]
            line.taxes = [(6, 0, taxes.ids)]
