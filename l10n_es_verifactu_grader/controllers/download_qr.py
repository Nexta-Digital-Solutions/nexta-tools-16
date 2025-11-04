from odoo import http
from odoo.http import request
import qrcode
import base64
import io


class VerifactuDownloadQRController(http.Controller):

    @http.route(
        "/verifactu/download_qr/<int:invoice_id>",
        type="http",
        auth="user",
        website=True,
    )
    def download_qr(self, invoice_id, **kwargs):
        # Buscar la factura
        invoice = request.env["account.move"].sudo().browse(invoice_id)
        if not invoice.exists():
            return request.not_found()

        # Generar el QR Code con la URL de verificación
        verification_url = (
            f"https://verifactu.aeat.es/verify/{invoice.verifactu_hash[:16]}"
        )
        qr = qrcode.make(verification_url)
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        buffer.seek(0)

        # Devolver el archivo como PNG
        response = request.make_response(
            buffer.read(),
            headers=[
                ("Content-Type", "image/png"),
                (
                    "Content-Disposition",
                    f'attachment; filename=verifactu_{invoice.name.replace("/", "_")}.png',
                ),
            ],
        )
        return response
