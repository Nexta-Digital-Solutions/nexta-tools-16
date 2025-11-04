# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
import requests
import re
from odoo.exceptions import UserError
from odoo import _, fields
from ..utils.cert_handler import VerifactuCertHandler
from ..utils.invoice_type_resolve import VerifactuTipoFacturaResolver  # <-- para tipo factura

# Reglas oficiales (referencia):
# https://prewww2.aeat.es/static_files/common/internet/dep/aplicaciones/es/aeat/tikeV1.0/cont/ws/errores.properties

# Errores que causan rechazo explícito del registro (AEAT recibe el XML y lo rechaza)
REJECTION_ERROR_CODES = set(list(range(4102, 4141)) + list(range(1100, 1300)) + [3001, 3002, 3003, 3004])

# Errores que permiten aceptación con errores (no deben causar estado 'rejected')
ACCEPTED_WITH_ERRORS_CODES = set(list(range(2000, 2009)) + [3000])  # 2000–2008 + 3000 (duplicado aceptado)

class VerifactuSender(object):

    def __init__(self, invoice):
        self.invoice = invoice

    # -------------------------
    # Helpers snapshot (sin mixin)
    # -------------------------
    def _clean_es_nif(self, v):
        v = (v or '').upper()
        v = ''.join(ch for ch in v if ch.isalnum())
        if v.startswith('ES'):
            v = v[2:]
        return v

    def _compute_tipo_factura_now(self, inv):
        try:
            return VerifactuTipoFacturaResolver.resolve(inv)
        except Exception:
            mt = getattr(inv, 'move_type', None) or getattr(inv, 'type', None) or ''
            return 'R1' if 'refund' in mt else 'F1'

    def _get_invoice_name(self, inv):
        return getattr(inv, 'name', None) or getattr(inv, 'number', None) or ''

    def _get_invoice_date(self, inv):
        return getattr(inv, 'invoice_date', None) or getattr(inv, 'date_invoice', None) or False

    def _current_idfactu_tuple(self, inv):
        emisor_nif = self._clean_es_nif(getattr(inv.company_id, 'vat', '') or '')
        return (emisor_nif, self._get_invoice_name(inv), self._get_invoice_date(inv), self._compute_tipo_factura_now(inv))

    def _last_idfactu_tuple(self, inv):
        return (
            getattr(inv, 'verifactu_last_emisor_nif', '') or '',
            getattr(inv, 'verifactu_last_numero', '') or '',
            getattr(inv, 'verifactu_last_fecha', False) or False,
            getattr(inv, 'verifactu_last_tipo', '') or '',
        )

    def _save_snapshot_after_send(self, inv):
        emisor, num, fecha, tipo = self._current_idfactu_tuple(inv)
        inv.sudo().write({
            'verifactu_last_emisor_nif': emisor,
            'verifactu_last_numero': num,
            'verifactu_last_fecha': fecha,
            'verifactu_last_tipo': tipo,
        })

    def _preflight_reset_if_idfactu_changed(self, inv):
        """Si cambió el IDFactura respecto al último snapshot, resetea flags para forzar envío como nuevo."""
        last = self._last_idfactu_tuple(inv)
        curr = self._current_idfactu_tuple(inv)
        # Si no hay snapshot previo, no hacemos nada
        if last == ('', '', False, ''):
            return
        if curr != last:
            inv.sudo().write({
                'verifactu_sent': False,
                'verifactu_sent_with_errors': False,
                'verifactu_processed': False,
                'verifactu_status': 'draft',
            })

    # -------------------------
    # Envío
    # -------------------------
    def send(self, signed_xml_str, attachment):
        invoice = self.invoice
        company = invoice.company_id

        endpoint_config = invoice.env["verifactu.endpoint.config"].search([
            ("company_id", "=", company.id)
        ], limit=1)

        if (not endpoint_config) or (not endpoint_config.endpoint_url):
            msg = _("⚠️ Endpoint no configurado. Se ha generado el archivo, pero no se ha podido enviar.")
            self._post_message(msg, attachment)
            invoice.verifactu_sent = False
            invoice.verifactu_sent_with_errors = False
            invoice.verifactu_processed = False
            invoice.verifactu_status = "error"
            return signed_xml_str

        try:
            # Preflight: si el IDFactura cambió, resetea flags aquí (sin hooks)
            try:
                self._preflight_reset_if_idfactu_changed(invoice)
            except Exception:
                pass

            with VerifactuCertHandler(endpoint_config.cert_pfx, endpoint_config.cert_password) as cert_handler:
                response = requests.post(
                    endpoint_config.endpoint_url,
                    data=signed_xml_str.encode("utf-8"),
                    headers={"Content-Type": "application/xml"},
                    cert=(cert_handler.cert_path, cert_handler.key_path),
                    timeout=30
                )

            # Parse estructurado
            res = self.parse_response(response.text)
            summary = res.get("summary")
            detail  = res.get("detail")
            status  = res.get("status")
            now = fields.Datetime.now()

            self._post_message(summary, attachment, detailed_error=detail)

            # Actualiza estados de forma explícita
            if status == "sent":
                invoice.verifactu_sent = True
                invoice.verifactu_sent_with_errors = False
                invoice.verifactu_processed = False
                invoice.verifactu_status = "sent"
                invoice.verifactu_date_sent = now
                invoice._log_verifactu_status("sent")
                # Guarda snapshot del IDFactura enviado
                try:
                    self._save_snapshot_after_send(invoice)
                except Exception:
                    pass

            elif status == "accepted_with_errors":
                invoice.verifactu_sent = False
                invoice.verifactu_sent_with_errors = True
                invoice.verifactu_processed = False
                invoice.verifactu_status = "accepted_with_errors"
                invoice.verifactu_date_sent = now
                invoice._log_verifactu_status("accepted_with_errors")
                try:
                    self._save_snapshot_after_send(invoice)
                except Exception:
                    pass

            elif status == "canceled":
                invoice.verifactu_sent = True
                invoice.verifactu_sent_with_errors = False
                invoice.verifactu_processed = False
                invoice.verifactu_status = "canceled"
                invoice.verifactu_date_sent = now
                invoice._log_verifactu_status("canceled")

            elif status == "rejected":
                invoice.verifactu_sent = False
                invoice.verifactu_sent_with_errors = False
                invoice.verifactu_processed = False
                invoice.verifactu_status = "rejected"
                invoice._log_verifactu_status("rejected")

            else:  # "error" u otros
                invoice.verifactu_sent = False
                invoice.verifactu_sent_with_errors = False
                invoice.verifactu_processed = False
                invoice.verifactu_status = "error"
                invoice._log_verifactu_status("error")

            return signed_xml_str

        except requests.exceptions.RequestException as e:
            # FALLO DE TRANSPORTE: no hubo SOAP válido en AEAT
            error_text = str(e)
            self._post_message(_("🛑 Error de transporte al contactar con VeriFactu: %s") % error_text,
                               attachment, detailed_error=error_text)
            invoice.verifactu_sent = False
            invoice.verifactu_sent_with_errors = False
            invoice.verifactu_processed = False
            invoice.verifactu_status = "transport_error"
            invoice._log_verifactu_status("transport_error")
            raise UserError(_("🛑 No se pudo contactar con VeriFactu. Reintenta o revisa la configuración."))

    # -------------------------
    # Parser de respuesta
    # -------------------------
    def parse_response(self, response_text):
        """
        Devuelve dict:
          {
            "status": "sent|accepted_with_errors|rejected|error|transport_error|canceled",
            "summary": <texto corto para chatter>,
            "code": <int o None>,
            "detail": <texto largo o None>
          }
        """
        inv = self.invoice
        display = (getattr(inv, 'name', None) or getattr(inv, 'number', None) or '???')

        if ("Anulada" in response_text) and ("Incorrecto" not in response_text):
            return {"status":"canceled","summary":_("🗑️ Factura %s anulada correctamente en VeriFactu.")%display,"code":None,"detail":response_text}

        if "Correcto" in response_text:
            return {"status":"sent","summary":_("✅ Factura %s enviada correctamente a VeriFactu.")%display,"code":None,"detail":None}

        code = self._extract_error_code(response_text)
        fault = self._extract_faultstring(response_text)

        if (code in ACCEPTED_WITH_ERRORS_CODES) or ("AceptadoConErrores" in response_text):
            detail = _("Código %s: Aceptada con errores. Requiere revisión posterior.") % code if code else response_text
            return {"status":"accepted_with_errors","summary":_("⚠️ Factura %s aceptada con errores por VeriFactu.")%display,"code":code,"detail":detail}

        if code in REJECTION_ERROR_CODES:
            detail = _("Código %s: %s") % (code, fault) if fault else response_text
            return {"status":"rejected","summary":_("🛑 Rechazada por VeriFactu (código %s). Revisa el detalle.")%(code or "?"),"code":code,"detail":detail}

        detail = _("Código %s: %s") % (code, fault) if fault else response_text
        return {"status":"error","summary":_("🛑 Error al enviar la factura a VeriFactu. Consulta el detalle."),"code":code,"detail":detail}

    # -------------------------
    # Extractores auxiliares
    # -------------------------
    def _extract_faultstring(self, xml_text):
        try:
            ns = {'env': 'http://schemas.xmlsoap.org/soap/envelope/'}
            root = ET.fromstring(xml_text)
            faultstring = root.find('.//env:Fault/env:faultstring', ns)
            return faultstring.text if faultstring is not None else None
        except ET.ParseError:
            return None

    def _extract_error_code(self, xml_text):
        try:
            matches = re.findall(r"\b(1[01]\d{2}|3\d{3}|4[01]\d{2})\b", xml_text)
            if matches:
                return int(matches[0])
        except Exception:
            pass
        return None

    # -------------------------
    # Mensajería
    # -------------------------
    def _post_message(self, message, attachment, detailed_error=None):
        already_posted = self.invoice.message_ids.filtered(
            lambda m: (m.body == message) and attachment and (attachment.id in m.attachment_ids.ids)
        )
        if not already_posted:
            self.invoice.message_post(body=message, message_type="comment")

        if detailed_error and (getattr(self.invoice, "verifactu_detailed_error_msg", None) != detailed_error):
            self.invoice.with_context(check_move_validity=False).sudo().write({
                "verifactu_detailed_error_msg": detailed_error
            })
