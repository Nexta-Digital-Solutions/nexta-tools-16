from odoo import _
from odoo.exceptions import UserError
from ..services.hash_calculator import VerifactuHashCalculator
from ..services.logger import VerifactuLogger

class VerifactuHashVerifier:
    def __init__(self, invoice, config):
        self.invoice = invoice
        self.config = config

    def verify(self):
        self.invoice.ensure_one()

        try:
            if not self.invoice.verifactu_hash_calculated_at:
                raise UserError(_("🛑 No se puede verificar el hash porque no hay fecha de cálculo registrada."))

            new_hash = VerifactuHashCalculator(self.invoice, self.config).compute_hash()
            current_hash = self.invoice.verifactu_hash or ""

            if new_hash == current_hash:
                message = f"✅ El hash actual para la factura {self.invoice.name} es correcto ({new_hash[:16]})"
            else:
                message = (
                    f"🛑 El hash actual no coincide para la factura {self.invoice.name}:\n"
                    f"- Guardado: {current_hash[:16]}\n"
                    f"- Esperado: {new_hash[:16]}"
                )

            VerifactuLogger(self.invoice).log(message)

        except Exception as e:
            error_msg = f"🛑 Error inesperado al verificar el hash: {str(e)}"
            VerifactuLogger(self.invoice).log(error_msg)
            raise UserError(_(error_msg))

        return True

