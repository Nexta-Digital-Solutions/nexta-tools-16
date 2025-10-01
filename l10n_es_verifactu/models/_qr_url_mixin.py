# verifactu/models/_qr_url_mixin.py
# Compatible Odoo 11 → 18

from odoo import models, fields, api, release

class VerifactuQRUrlMixin(models.AbstractModel):
    _name = "verifactu.qr.url.mixin"
    _description = "Mixin para almacenar URL de QR VeriFactu"

    # Campo persistente (se creará en el modelo que herede el mixin)
    verifactu_qr_url = fields.Char(string="VeriFactu QR URL", readonly=True, copy=False)

    def _vf_resolve_config(self, company_id):
        return self.env["verifactu.endpoint.config"].sudo().search([("company_id", "=", company_id)], limit=1)

    def _vf_is_noverifactu(self, inv):
        # Ajusta a tu lógica real si tienes un flag específico
        return bool(getattr(inv, "verifactu_noverifactu", False))

    def _vf_generate_and_store_qr_url(self):
        """Genera la URL del QR y la guarda en verifactu_qr_url (no rompe el flujo si falla)."""
        # OJO: ruta real del generador (tú lo tienes en verifactu/services/qr_content.py)
        from ..verifactu.services.qr_content import VerifactuQRContentGenerator

        for inv in self:
            try:
                config = self._vf_resolve_config(inv.company_id.id)
                if not config:
                    inv.sudo().write({"verifactu_qr_url": False})
                    continue

                factura_verificable = not self._vf_is_noverifactu(inv)
                gen = VerifactuQRContentGenerator(inv, config, factura_verificable=factura_verificable)
                url = gen.generate_content()
                inv.sudo().write({"verifactu_qr_url": url})
            except Exception:
                inv.sudo().write({"verifactu_qr_url": False})
                continue


# ---------- v13+ (account.move) ----------
if release.version_info[0] >= 13:

    class AccountMove_VerifactuQR(models.Model):
        _inherit = ["account.move", "verifactu.qr.url.mixin"]
        _name = "account.move"

        def action_post(self):
            res = super(AccountMove_VerifactuQR, self).action_post()
            try:
                self._vf_generate_and_store_qr_url()
            except Exception:
                pass
            return res

        # Métodos llamados por los botones de la vista
        def action_open_verifactu_qr_url(self):
            self.ensure_one()
            url = (self.verifactu_qr_url or "").strip()
            if not url:
                return False
            return {
                "type": "ir.actions.act_url",
                "url": url,
                "target": "new",
            }

        def action_regenerate_verifactu_qr_url(self):
            self.ensure_one()
            try:
                self._vf_generate_and_store_qr_url()
            except Exception:
                pass
            return True

# ---------- v11–12 (account.invoice) ----------
else:

    class AccountInvoice_VerifactuQR(models.Model):
        _inherit = ["account.invoice", "verifactu.qr.url.mixin"]
        _name = "account.invoice"

        def action_invoice_open(self):
            res = super(AccountInvoice_VerifactuQR, self).action_invoice_open()
            try:
                self._vf_generate_and_store_qr_url()
            except Exception:
                pass
            return res

        def action_open_verifactu_qr_url(self):
            self.ensure_one()
            url = (self.verifactu_qr_url or "").strip()
            if not url:
                return False
            return {
                "type": "ir.actions.act_url",
                "url": url,
                "target": "new",
            }

        def action_regenerate_verifactu_qr_url(self):
            self.ensure_one()
            try:
                self._vf_generate_and_store_qr_url()
            except Exception:
                pass
            return True
