# Desarrollado por Juan Ormaechea (Mr. Rubik) — Todos los derechos reservados
# Este módulo está protegido por la Odoo Proprietary License v1.0
# Cualquier redistribución está prohibida sin autorización expresa.

import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
from odoo import _, models, fields, api
from odoo.exceptions import UserError
import hashlib
import logging
import base64
import qrcode
from io import BytesIO

from cryptography.hazmat.backends import default_backend
import lxml.etree as LET
from signxml import XMLSigner, methods
from datetime import datetime, timedelta, timezone
import re
import platform
import socket
from ..verifactu.services.xml_builder.xml_builder import VerifactuXMLBuilder
from ..verifactu.services.xml_signer import VerifactuXMLSigner
from ..verifactu.services.attachment import VerifactuAttachmentService
from ..verifactu.services.hash_calculator import VerifactuHashCalculator
from ..verifactu.services.logger import VerifactuLogger
from ..verifactu.services.show_notification import VerifactuNotifier
from ..verifactu.services.xml_sender import VerifactuSender
from ..verifactu.services.qr_content import VerifactuQRContentGenerator
from ..verifactu.services.resender import VerifactuResender
from ..verifactu.services.chain_verifier import VerifactuChainVerifier
from ..verifactu.services.event_exporter import VerifactuEventExporter
from ..verifactu.services.hash_verifier import VerifactuHashVerifier
from ..verifactu.services.integrity_verifier import VerifactuIntegrityVerifier
from ..verifactu.services.xml_builder.xml_builder_simple import VerifactuSimpleXMLBuilder
from ..verifactu.services.anomaly_detector import VerifactuAnomalyDetector
from ..verifactu.services.xml_builder.envelope_builder import VerifactuEnvelopeBuilder
from ..verifactu.services.xml_builder.xml_builder_subsanacion import VerifactuXMLBuilderSubsanacion
from ..verifactu.services.xml_builder.xml_builder_anulacion import VerifactuXMLBuilderAnulacion
from ..verifactu.services.xml_builder.envelope_builder_anluacion import (
    VerifactuEnvelopeBuilderAnulacion,
)
from ..verifactu.services.xml_builder.xml_builder_no_verifactu_subsanacion import VerifactuXMLBuilderNoVerifactuSubsanacion
from ..verifactu.services.xml_builder.no_verifactu_xml_builder import VerifactuXMLBuilderNoVerifactu
from ..verifactu.services.xml_builder.xml_builder_no_verifactu_anulacion import VerifactuXMLBuilderNoVerifactuAnulacion


_logger = logging.getLogger(__name__)

# ---------- Helpers compatibles 11→18 ----------
def _vf_clean_es(vat):
    vat = (vat or "").strip().upper()
    if vat.startswith("ES"):
        vat = vat[2:]
    return vat.replace(" ", "").replace("-", "").replace(".", "")

def _vf_get_move_type(inv):
    """Devuelve 'out_invoice' / 'out_refund' compatible 11→18."""
    # v13+: move_type
    mt = getattr(inv, "move_type", None)
    if mt:
        return mt
    # v11/12: type
    return getattr(inv, "type", "")

def _vf_get_name(inv):
    """Compat de número/serie."""
    return getattr(inv, "name", None) or getattr(inv, "number", None) or ""

def _vf_get_date(inv):
    """Compat de fecha expedición."""
    return getattr(inv, "invoice_date", None) or getattr(inv, "date_invoice", None)

def _vf_resolve_tipo_factura(inv):
    """Usa tu resolver si está disponible; fallback básico."""
    try:
        # Import local para no romper si no existe en esta base
        from ..verifactu.utils.invoice_type_resolve import VerifactuTipoFacturaResolver
        return VerifactuTipoFacturaResolver.resolve(inv)
    except Exception:
        mt = _vf_get_move_type(inv)
        # F1: normal; R1: rectificativa (fallback simple)
        return "R1" if mt == "out_refund" else "F1"

def _vf_current_id_tuple(inv):
    """Tupla actual (IDEmisor, NumSerie, Fecha(dd-mm-YYYY), TipoFactura)."""
    company_vat = _vf_clean_es(getattr(inv.company_id, "vat", ""))
    num = _vf_get_name(inv)
    d = _vf_get_date(inv)
    fecha = d.strftime("%d-%m-%Y") if d else ""
    tipo = _vf_resolve_tipo_factura(inv)
    return (company_vat, num, bool(d), tipo)

def _vf_last_id_tuple(inv):
    """
    Lee el último snapshot guardado si existe.
    Campos soportados (usa los que tengas; si no, fallback vacío):
      - verifactu_last_id_emisor
      - verifactu_last_num_serie
      - verifactu_last_fecha_bool (o verifactu_last_fecha_str)
      - verifactu_last_tipo_factura
    """
    idemisor = getattr(inv, "verifactu_last_id_emisor", "") or ""
    num = getattr(inv, "verifactu_last_num_serie", "") or ""
    # admitimos bool o string
    fecha_bool = getattr(inv, "verifactu_last_fecha_bool", None)
    if fecha_bool is None:
        fecha_bool = bool(getattr(inv, "verifactu_last_fecha_str", "") or False)
    tipo = getattr(inv, "verifactu_last_tipo_factura", "") or ""
    return (idemisor, num, bool(fecha_bool), tipo)

def _vf_save_id_snapshot(inv):
    """Guarda el snapshot actual si tienes esos campos definidos (silencioso si no)."""
    try:
        idemisor, num, fecha_ok, tipo = _vf_current_id_tuple(inv)
        vals = {}
        if hasattr(inv, "verifactu_last_id_emisor"):
            vals["verifactu_last_id_emisor"] = idemisor
        if hasattr(inv, "verifactu_last_num_serie"):
            vals["verifactu_last_num_serie"] = num
        if hasattr(inv, "verifactu_last_fecha_bool"):
            vals["verifactu_last_fecha_bool"] = fecha_ok
        elif hasattr(inv, "verifactu_last_fecha_str"):
            vals["verifactu_last_fecha_str"] = "1" if fecha_ok else ""
        if hasattr(inv, "verifactu_last_tipo_factura"):
            vals["verifactu_last_tipo_factura"] = tipo
        if vals:
            inv.sudo().with_context(check_move_validity=False).write(vals)
    except Exception:
        _logger.debug("No se pudo guardar snapshot VeriFactu para %s", inv.id)

def _vf_reset_to_pending(inv):
    """Lleva la factura a estado 'pending' para permitir reenvío/recálculo."""
    vals = {
        "verifactu_status": "pending",
        "verifactu_sent": False,
        "verifactu_sent_with_errors": False,
        "verifactu_processed": False,
    }
    # Mantén verifactu_date_sent si quieres histórico; aquí no lo tocamos
    inv.sudo().with_context(check_move_validity=False).write(vals)



class AccountMove(models.Model):
    _inherit = "account.move"

    verifactu_last_emisor_nif = fields.Char(readonly=True)
    verifactu_last_numero = fields.Char(readonly=True)
    verifactu_last_fecha = fields.Date(readonly=True)
    verifactu_last_tipo = fields.Char(readonly=True)
    
    verifactu_detailed_error_msg = fields.Text(
        string="Mensaje de error VeriFactu (en detalle)"
    )

    verifactu_qr = fields.Binary(
        "QR VeriFactu", help="Código QR generado tras la validación VeriFactu."
    )

    verifactu_is_active = fields.Boolean(
        string="VeriFactu Activo",
        default=True,
        help="Indica si VeriFactu está activo para esta compañía.",
    )
    
    verifactu_requerimiento = fields.Char(
        string="Referencia de Requerimiento AEAT",
        help="Código oficial del requerimiento recibido por la AEAT. Obligatorio en el modo No VeriFactu.",
    )

    verifactu_date_sent = fields.Datetime(
        string="Fecha de envío VeriFactu",
        readonly=True,
        help="Fecha y hora en que se envió la factura a la AEAT mediante VeriFactu.",
    )
        
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        required=True,
    )

    anomaly_cron_enabled = fields.Boolean(
        string="Detección Automática Activa",
        compute="_compute_anomaly_cron_enabled",
        store=False,
    )

    verifactu_sent = fields.Boolean(
        string="Enviado a VeriFactu sin errores", default=False
    )
    verifactu_sent_with_errors = fields.Boolean(
        string="Enviado a VeriFactu con errores", default=False
    )
    verifactu_processed = fields.Boolean(string="VeriFactu procesao", default=False)
    verifactu_status = fields.Selection(
        [
            ("pending", "Pendiente"),
            ("sent", "Enviado"),
            ("accepted_with_errors", "Aceptado con errores"),
            ("error", "Error"),
            ("rejected", "Rechazado"),
            ("canceled", "anulado"),
            ("duplicated", "Duplicado"),  # opcional, si deseas diferenciar
        ],
        default="pending",
        string="Estado VeriFactu",
        tracking=True,
    )

    verifactu_hash_calculated_at = fields.Datetime(
        string="Fecha de Cálculo del Hash", readonly=True
    )

    invoice_date_operation = fields.Date(
        string="Fecha de Operación",
        help="Indica la fecha en la que se realiza la operación económica real si es distinta a la fecha de expedición.",
    )

    verifactu_soap_xml = fields.Binary(string="Verifactu SOAP XML", attachment=False)

    verifactu_generated = fields.Boolean(
        string="XML VeriFactu generado",
        default=False,
        help="Indica si se ha generado el XML para esta factura, aunque no se haya enviado todavía."
    )

    verifactu_error_msg = fields.Text(string="Mensaje de error VeriFactu")

    verifactu_qr_image = fields.Binary(
        string="VeriFactu QR",
        compute="_compute_verifactu_qr_image",
        store=True,
        attachment=True,
    )
    
    verifactu_dev_hash = fields.Char(string='Verifactu Hash Dev', default='mrrubik:vf-v1.3.20250611', readonly=True)
    
    verifactu_hash = fields.Char(string="Hash VeriFactu", readonly=True)
    verifactu_previous_hash = fields.Char(
        string="Hash Anterior VeriFactu", readonly=True
    )
    verifactu_event_logs = fields.Many2many(
        "verifactu.event.log", string="Registros de Eventos", readonly=True
    )

    verifactu_issued_at = fields.Datetime(string="Fecha y hora de emisión VeriFactu")

    verifactu_base_coste = fields.Monetary(
        string="Base imponible a coste",
        compute="_compute_verifactu_base_coste",
        store=True,
        currency_field='currency_id'
    )
    
    verifactu_status_logs = fields.One2many(
    "verifactu.status.log", "invoice_id",
    string="Historial de Estado VeriFactu",
    )
    
    show_qr_always = fields.Boolean(
        string="Mostrar QR tributario",
        compute="_compute_show_qr_always",
        store=False  # o True si te interesa indexarlo
    )

    @api.depends("company_id")
    def _compute_show_qr_always(self):
        config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)
        for move in self:
            move.show_qr_always = config.show_qr_always
       

    
    def _log_verifactu_status(self, status, notes=""):
        self.ensure_one()
        self.env["verifactu.status.log"].create({
            "invoice_id": self.id,
            "status": status,
            "notes": notes,
        })


    @api.depends('invoice_line_ids', 'invoice_line_ids.product_id', 'invoice_line_ids.quantity')
    def _compute_verifactu_base_coste(self):
        for move in self:
            coste_total = 0.0
            for line in move.invoice_line_ids:
                # Si no hay producto o cantidad, se ignora la línea
                if line.product_id and line.quantity:
                    coste_total += line.product_id.standard_price * line.quantity
            move.verifactu_base_coste = coste_total

    def _vf_check_readiness(self, config):
        """
        Devuelve (ok, msgs) indicando si la factura puede generar/enviar a VeriFactu.
        No lanza excepción: solo prepara mensajes para el log.
        """
        msgs = []

        # Config básica
        if not (config and config.cert_pfx and config.cert_password):
            msgs.append("certificado digital no configurado (.pfx + contraseña)")
        if not (config and config.endpoint_url):
            msgs.append("endpoint de VeriFactu no configurado")

        # Licencia (suave: no bloquea, solo avisa)
        try:
            gate_ok = self.env["verifactu.license.gate"]._is_valid()
        except Exception as e:
            gate_ok = False
            msgs.append(f"no se pudo verificar licencia ({e})")

        if not gate_ok:
            msgs.append("licencia no válida o no configurada")

        return (len(msgs) == 0, msgs)

    def _vf_log_and_skip(self, msgs, tail=""):
        text = "⚠️ Configuración/licencia incompleta de VeriFactu: " + " | ".join(msgs)
        if tail:
            text += ". %s" % tail
        self.message_post(body=text)

    def _vf_safe_call(self, func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.message_post(body="🛑 Error VeriFactu: %s" % e)
            _logger.exception("Error VeriFactu en %s: %s", getattr(func, "__name__", func), e)
            return None

    def _vf_after_post(self):
        """Bloque común ejecutado tras post/confirm según versión."""
        config = (
            self.env["verifactu.endpoint.config"]
            .sudo()
            .search([("company_id", "=", self.env.user.company_id.id)], limit=1)
        )

        for inv in self:
            # Aviso de updates (no bloqueante)
            try:
                self.env["verifactu.update.checker"].check_and_notify_if_needed(inv)
            except Exception:
                pass

            # Solo ventas cliente (v11/12)
            if getattr(inv, "type", "") != "out_invoice":
                continue

            # Fecha de emisión VeriFactu
            if not getattr(inv, "verifactu_issued_at", False):
                inv.verifactu_issued_at = fields.Datetime.now()

            # Readiness
            ok, msgs = inv._vf_check_readiness(config)
            if not ok:
                inv._vf_log_and_skip(msgs, tail="Ve a Ajustes → VeriFactu para completarla.")
                continue

            # Envío / solo generar
            if inv.should_send_to_verifactu(config):
                inv._vf_safe_call(inv.send_xml)
            else:
                inv._vf_safe_call(inv.only_generate_xml_never_send)
 

    def action_post(self):
        res = super(AccountMove, self).action_post()

        config = (
            self.env["verifactu.endpoint.config"]
            .sudo()
            .search([("company_id", "=", self.env.company.id)], limit=1)
        )

        for inv in self:
            # Notificación no bloqueante
            try:
                self.env["verifactu.update.checker"].check_and_notify_if_needed(inv)
            except Exception:
                pass

            # Solo ventas/abonos cliente y ya posteadas
            if _vf_get_move_type(inv) not in ("out_invoice", "out_refund"):
                continue
            if inv.state != "posted":
                continue

            # (1) Detectar cambio de IDFactura vs snapshot → reset a 'pending'
            last = _vf_last_id_tuple(inv)
            if last != ("", "", False, ""):
                curr = _vf_current_id_tuple(inv)
                if curr != last:
                    try:
                        from ..verifactu.services.logger import VerifactuLogger
                        VerifactuLogger(inv).log("ℹ️ IDFactura cambiado (NIF/Num/Fecha/Tipo) → estado 'pending'.")
                    except Exception:
                        pass
                    _vf_reset_to_pending(inv)

            # (2) Fecha emisión VeriFactu si falta
            if not getattr(inv, "verifactu_issued_at", False):
                inv.verifactu_issued_at = fields.Datetime.now()

            # (3) Readiness
            ok, msgs = inv._vf_check_readiness(config)
            if not ok:
                inv._vf_log_and_skip(msgs, tail="Ve a Ajustes > VeriFactu para completarla.")
                continue

            # (4) Recalcular QR / Hash (a prueba de errores)
            try:
                from ..verifactu.services.logger import VerifactuLogger
                VerifactuLogger(inv).log("⚠️ Factura modificada")
            except Exception:
                pass

            if getattr(config, "show_qr_always", False):
                try:
                    from ..verifactu.services.qr_content import VerifactuQRContentGenerator
                    qr_bytes = VerifactuQRContentGenerator(inv, config, factura_verificable=True).generate_qr_binary()
                    inv.verifactu_qr = base64.b64encode(qr_bytes).decode("utf-8") if qr_bytes else False
                except Exception as e:
                    try:
                        VerifactuLogger(inv).log("⚠️ Error generando QR: %s" % e)
                    except Exception:
                        pass

            try:
                from ..verifactu.services.hash_calculator import VerifactuHashCalculator
                VerifactuHashCalculator(inv, config).compute_and_update(force_recalculate=True)
            except Exception as e:
                try:
                    VerifactuLogger(inv).log("⚠️ Error recalculando hash: %s" % e)
                except Exception:
                    pass

            # (5) Envío / solo generar
            if inv.should_send_to_verifactu(config):
                inv._vf_safe_call(inv.send_xml)
            else:
                inv._vf_safe_call(inv.only_generate_xml_never_send)

            # (6) Guardar nuevo snapshot del IDFactura tras post
            _vf_save_id_snapshot(inv)

        return res

    def should_send_to_verifactu(self, config):
        return (
            self.move_type in ("out_invoice", "out_refund") and
            config.auto_send_to_verifactu and
            config.cert_pfx and config.cert_password
        )


    @api.model
    def create(self, vals):
        invoice = super().create(vals)
        return invoice

    def write(self, vals):
        if not vals:
            return super().write(vals)

        res = super().write(vals)

        critical_fields = ["name", "invoice_date", "amount_total", "amount_tax", "move_type"]
        if any(f in vals for f in critical_fields):
            config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)

            for rec in self:
                if rec.state != "posted":
                    continue

                ok, msgs = rec._vf_check_readiness(config)
                if not ok:
                    rec._vf_log_and_skip(msgs, tail="Se omitió el recálculo de QR y hash.")
                    continue

                # A partir de aquí no debe romper el flujo aunque algo falle:
                VerifactuLogger(rec).log("⚠️ Factura modificada")

                # Recalcular QR si procede
                if getattr(config, "show_qr_always", False):
                    try:
                        qr_bytes = VerifactuQRContentGenerator(rec, config, factura_verificable=True).generate_qr_binary()
                        rec.verifactu_qr = base64.b64encode(qr_bytes).decode("utf-8") if qr_bytes else False
                    except Exception as e:
                        VerifactuLogger(rec).log(f"⚠️ Error generando QR: {e}")

                # Recalcular hash
                try:
                    VerifactuHashCalculator(rec, config).compute_and_update(force_recalculate=True)
                except Exception as e:
                    VerifactuLogger(rec).log(f"⚠️ Error recalculando hash: {e}")

        return res
    
    def open_error_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "verifactu.error.codes.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
            },
        }

    def open_requirement_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "verifactu.requirement.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_ref_requerimiento": self.verifactu_requerimiento or "",
                "active_id": self.id,
            },
        }


    def stop_no_verifactu_mode(self):
        self.verifactu_generated = False
        self.log_system_event("✅ Fin del modo NO VERI*FACTU.Establece de nuevo una url (endoint) de VeriFactu.")
        self.verifactu_is_active = True

        # Vaciar el campo del endpoint de requerimiento si es específico del modo No VeriFactu
        config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)
        config.endpoint_url = ""

        msg = "⚠️ Fin del modo NO VERI*FACTU.Establece de nuevo una url (endoint) de VeriFactu."
        VerifactuLogger(self).log(msg)
        
    
    
    def action_open_verifactu_help(self):
        wizard = self.env['verifactu.help.wizard'].create({})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'verifactu.help.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }




    def detect_anomalies(self):
        anomalies = []
        for invoice in self.env["account.move"].search(
            [
                ("verifactu_sent", "=", True),
                ("verifactu_sent_with_errors", "=", True),
                ("verifactu_processed", "=", True),
            ]
        ):
            if not self.verify_integrity():
                anomalies.append(invoice)

        # Evento global
        if anomalies:
            msg = f"🛑 Detectadas anomalías en {len(anomalies)} facturas."
            VerifactuLogger(self).log(msg)
        else:
            msg = f"✅ No se detectaron anomalías en los registros de facturación."
            VerifactuLogger(self).log(msg)

    # En account_move.py
    def toggle_anomaly_cron(self):
        detector = VerifactuAnomalyDetector(self.env)
        if detector.is_cron_enabled():
            detector.disable_cron()
        else:
            detector.enable_cron()
            
    @api.model
    def cron_send_pending_verifactu(self):
        

        for company in self.env['res.company'].search([]):
            
            config = self.env['verifactu.endpoint.config'].sudo().search([
                ('company_id', '=', company.id)
            ], limit=1)
            _logger.info(f"[VeriFactu][{company.name}] Cron ejecutado. Config activa: {bool(config)}. Envío automático activo: {bool(config.auto_send_to_verifactu)}")


            invoices = self.with_company(company).sudo().search([
                ('company_id', '=', company.id),
                ('state', '=', 'posted'),
                ('move_type', 'in', ('out_invoice', 'out_refund')),
                ('verifactu_status', 'in', ['pending', 'error']),
                ('verifactu_generated', '=', True),
            ], limit=5, order='invoice_date asc, id asc')

            for invoice in invoices:
                try:
                    invoice.send_xml()
                except Exception as e:
                    _logger.warning(f"[VeriFactu][{company.name}] Error al enviar {invoice.name}: {e}")

    @api.depends()
    def _compute_anomaly_cron_enabled(self):
        # Detecta si el CRON está activo
        cron = self.env.ref(
            "l10n_es_verifactu.ir_cron_detect_anomalies", raise_if_not_found=False
        )
        active = bool(cron and cron.active)
        for record in self:
            record.anomaly_cron_enabled = active

    def export_event_records(self):
        return VerifactuEventExporter(self).export()

    def verify_verifactu_hash(self):
        self.ensure_one()
        config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)
        VerifactuHashVerifier(self,config).verify()
        return True

    def verify_verifactu_signature(self):
        self.ensure_one()
        try:
            xml_string = VerifactuSimpleXMLBuilder(self).build()

            # Obtener configuración con el certificado
            config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)
            signed_xml = VerifactuXMLSigner(config).sign(xml_string)

            VerifactuLogger(self).log(
                f"✅ Firma electrónica verificada para la factura {self.name}"
            )
            return True

        except Exception as e:
            VerifactuLogger(self).log(
                f"🛑 Error al verificar la firma electrónica: {str(e)}"
            )
            raise UserError(_(f"Error al verificar la firma electrónica: {str(e)}"))

    def verify_integrity(self):
        config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)
        return VerifactuIntegrityVerifier(self,config).verify()

    def verify_chain(self):
        return VerifactuChainVerifier(self).verify()

    def log_system_event(self, message):
        event = self.env["verifactu.event.log"].create({"name": message})
        _logger.info(message)
        return event

    def log_backup_restore(self):
        self.log_system_event("🔄 Restauración de copia de seguridad detectada.")

    def log_event_summary(self):
        self.log_system_event("📊 Generación de resumen de eventos.")

    def _generate_verifactu_xml(self):
        return VerifactuSimpleXMLBuilder(self).build()

    @api.depends("state", "verifactu_status")
    def _compute_verifactu_qr_image(self):
        config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)
        gate = self.env["verifactu.license.gate"]  # gate soft
        for rec in self:
            # valor por defecto
            rec.verifactu_qr_image = False

            # solo en posted
            if rec.state != "posted":
                continue

            should_generate = (
                (config and config.show_qr_always)
                or rec.verifactu_status in ("sent", "accepted_with_errors", "canceled", "rejected", "error")
            )

            if not should_generate:
                continue

            # 1) licencia (suave: no bloquea, solo evita generar QR del módulo)
            if not gate.ensure_valid(hard=False):
                VerifactuLogger(rec).log(
                    "ℹ️ No se genera QR de VeriFactu porque la licencia no es válida o falta el token."
                )
                continue

            # 2) config mínima (suave)
            missing_cert = not (config and config.cert_pfx and config.cert_password)
            missing_endpoint = not (config and config.endpoint_url)
            if missing_cert or missing_endpoint:
                msgs = []
                if missing_cert:
                    msgs.append("certificado digital no configurado (.pfx + contraseña)")
                if missing_endpoint:
                    msgs.append("endpoint de VeriFactu no configurado")
                VerifactuLogger(rec).log(
                    "ℹ️ QR omitido por configuración incompleta: " + " | ".join(msgs)
                )
                continue

            # 3) generar QR (nunca debe tocar firma ni abrir el .pfx)
            try:
                qr_bytes = VerifactuQRContentGenerator(
                    rec, config, factura_verificable=True
                ).generate_qr_binary()
                rec.verifactu_qr_image = (
                    base64.b64encode(qr_bytes).decode("ascii") if qr_bytes else False
                )
            except Exception as e:
                VerifactuLogger(rec).log(f"⚠️ No se pudo generar el QR: {e}")
                rec.verifactu_qr_image = False

    def get_verifactu_qr_content(self):
        config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)
        return VerifactuQRContentGenerator(self,config,self.verifactu_is_active).generate_content()

    def get_verifactu_qr_image_binary(self):
        config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)
        return VerifactuQRContentGenerator(self,config,self.verifactu_is_active).generate_qr_binary()
    
    def only_generate_xml_never_send(self):
        """Genera el XML (VeriFactu o No-VeriFactu) sin enviarlo a la AEAT."""
        self.ensure_one()
                # 🔐 Restricción: no permitir enviar facturas con fecha anterior a otra ya enviada
        if self.verifactu_is_active:
            newer_sent_invoice = self.search([
                ('id', '!=', self.id),
                ('verifactu_status', 'in', ('sent', 'accepted_with_errors')),
                ('invoice_date', '>', self.invoice_date),
            ], limit=1)

            if newer_sent_invoice:
                raise UserError(_(
                    "No se puede enviar esta factura a VeriFactu porque hay otra factura ya enviada "
                    "con una fecha posterior: %s (%s). Por favor, revisa el orden cronológico de tus facturas."
                ) % (newer_sent_invoice.name, newer_sent_invoice.invoice_date))
        if self.verifactu_is_active:
            self.prepare_verifactu_record()
        else:
            self.prepare_no_verifactu_record()
        VerifactuLogger(self).log("📄 XML generado sin envío, lo puedes descargar en la pestaña de VeriFactu")
        self.verifactu_generated = True



    
    def send_xml(self):
        self.ensure_one()
        config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)

        # 0) Gate de licencia: para ENVIAR (acción explícita) bloqueamos si no es válida
        gate = self.env["verifactu.license.gate"]
        if not gate.ensure_valid(hard=False):
            # Aviso visible y error explícito
            VerifactuLogger(self).log(
                "⛔ Licencia de VeriFactu inválida o no configurada. "
                "Introduce tu clave y pulsa 'Obtener/Actualizar token' en Ajustes > VeriFactu."
            )
            raise UserError(
                "⛔ Licencia de VeriFactu inválida o no configurada.\n"
                "Introduce tu clave y pulsa 'Obtener/Actualizar token' en Ajustes > VeriFactu."
            )

        # 1) Restricción cronológica (tu lógica original)
        if self.verifactu_is_active:
            newer_sent_invoice = self.search([
                ('id', '!=', self.id),
                ('verifactu_status', 'in', ('sent', 'accepted_with_errors')),
                ('invoice_date', '>', self.invoice_date),
            ], limit=1)
            if newer_sent_invoice:
                raise UserError(_(
                    "No se puede enviar esta factura a VeriFactu porque hay otra factura ya enviada "
                    "con una fecha posterior: %s (%s). Por favor, revisa el orden cronológico de tus facturas."
                ) % (newer_sent_invoice.name, newer_sent_invoice.invoice_date))

        # 2) Checks de configuración mínimos
        missing_cert = not (config and config.cert_pfx and config.cert_password)
        missing_endpoint = not (config and (config.endpoint_url or "").strip())
        if missing_cert or missing_endpoint:
            msgs = []
            if missing_cert:
                msgs.append("certificado digital no configurado (.pfx + contraseña)")
            if missing_endpoint:
                msgs.append("endpoint de VeriFactu no configurado")
            human_msg = " | ".join(msgs)
            VerifactuLogger(self).log(
                f"⚠️ Configuración incompleta de VeriFactu: {human_msg}. "
                "Ve a Ajustes > VeriFactu para completarla."
            )
            raise UserError(_("No se puede enviar la factura: %s.") % human_msg)

        # 3) Flujo de envío (reutiliza tu lógica)
        if self.verifactu_generated and self.verifactu_status in ("pending",):
            # Ya generado → solo enviar
            if self.verifactu_is_active:
                self.send_verifactu_record()
                _logger.warning(
                    f" 📄Enviando en modo  verifactu"
                )
            else:
                self.send_no_verifactu_record()
                _logger.warning(
                    f" 📄Enviando en modo  verifactu"
                )
        else:
            # Generar + enviar
            if self.verifactu_is_active:
                self.prepare_verifactu_record()
                self.send_verifactu_record()
                _logger.warning(
                    f" 📄Enviando en modo  verifactu"
                )
            else:
                self.prepare_no_verifactu_record()
                self.send_no_verifactu_record()
                _logger.warning(
                    f" 📄Enviando en modo NO verifactu"
                )
            self.verifactu_generated = True
    
    def prepare_no_verifactu_record(self):
        self.ensure_one()


        self._validate_verifactu_tax_rates()
        config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)

        VerifactuHashCalculator(self, config).compute_and_update(force_recalculate=True)

        if self.verifactu_status in ("sent", "accepted_with_errors"):
            builder = VerifactuXMLBuilderNoVerifactuSubsanacion(self, config)
        elif self.verifactu_status in ("rejected", "canceled"):
            builder = VerifactuXMLBuilderNoVerifactuSubsanacion(self, config, rechazo_previo=True)
        else:
            builder = VerifactuXMLBuilderNoVerifactu(self, config)

        raw_xml = builder.build()

        self.verifactu_soap_xml = base64.b64encode(raw_xml.encode("utf-8"))

        # Adjuntar pero no enviar aún
        VerifactuAttachmentService(self).attach_xml(raw_xml)


    
    def send_no_verifactu_record(self):
        self.ensure_one()

        if not self.verifactu_soap_xml:
            raise UserError(_("No se ha generado el XML. Ejecuta primero 'prepare_no_verifactu_record()'."))

        decoded_xml = base64.b64decode(self.verifactu_soap_xml).decode("utf-8")
        attachment = VerifactuAttachmentService(self).attach_xml(decoded_xml)

        VerifactuSender(self).send(decoded_xml, attachment)



    def prepare_verifactu_record(self):
        self.ensure_one()


        self._validate_verifactu_tax_rates()
        config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)

        VerifactuHashCalculator(self, config).compute_and_update(force_recalculate=True)

        # Selección de builder
        if self.verifactu_status in ("sent", "accepted_with_errors"):
            builder = VerifactuXMLBuilderSubsanacion(self, config)
        elif self.verifactu_status == "rejected":
            builder = VerifactuXMLBuilderSubsanacion(self, config, rechazo_previo=True)
        elif self.verifactu_status == "canceled":
            builder = VerifactuXMLBuilderSubsanacion(self, config, rechazo_previo=True)
        else:
            builder = VerifactuXMLBuilder(self, config)

        raw_xml = builder.build()
        signed_xml = raw_xml  # Omitida la firma

        soap_envelope = VerifactuEnvelopeBuilder(self, config=config).build(signed_xml)
        self.verifactu_soap_xml = base64.b64encode(soap_envelope.encode("utf-8"))

        qr_base64 = base64.b64encode(
            VerifactuQRContentGenerator(self, config, self.verifactu_is_active).generate_qr_binary()
        ).decode("utf-8")
        self.verifactu_qr = qr_base64

        # Adjuntar, pero sin enviar aún
        VerifactuAttachmentService(self).attach_xml(soap_envelope)



    def send_verifactu_record(self):
        self.ensure_one()

        if not self.verifactu_soap_xml:
            raise UserError(_("No se ha generado el XML. Ejecuta primero 'prepare_verifactu_record()'."))

        decoded_envelope = base64.b64decode(self.verifactu_soap_xml).decode("utf-8")
        attachment = VerifactuAttachmentService(self).attach_xml(decoded_envelope)

        VerifactuSender(self).send(decoded_envelope, attachment)

    def generate_verifactu_anulacion(self):
        self.ensure_one()
        
        if self.verifactu_status not in ("sent", "accepted_with_errors"):
            raise UserError(_(
                "No se puede generar una anulación porque esta factura no ha sido enviada aún a VeriFactu. "
                "Solo se puede anular si el estado es 'Enviado' o 'Enviado con errores'."
            ))


        self._validate_verifactu_tax_rates()
        config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)

        # 1. Calcular el hash y guardarlo
        hash_value = VerifactuHashCalculator(self,config).compute_cancellation_hash()
        self.verifactu_hash = hash_value

        # 2. Seleccionar el builder según si es subsanación o no

        if self.verifactu_status == "pending":
            builder = VerifactuXMLBuilderAnulacion(
                self, config, sin_Factura_anterior=True
            )
        elif self.verifactu_status == "rejected" or self.verifactu_status == "error":
            builder = VerifactuXMLBuilderAnulacion(self, config, rechazo_previo=True)
        else:
            builder = VerifactuXMLBuilderAnulacion(self, config)

        # 3. Construir el XML
        raw_xml = builder.build()

        # 4. Firmar el XML
        config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)
        # signed_xml = VerifactuXMLSigner(config).sign(raw_xml)

        # Omitir la firma
        signed_xml = raw_xml

        # Envolver el XML sin firma
        soap_envelope = VerifactuEnvelopeBuilderAnulacion(self, config=config).build(signed_xml)

        # 6. Generar y guardar el QR
        qr_base64 = base64.b64encode(
            VerifactuQRContentGenerator(self,config,self.verifactu_is_active).generate_qr_binary()
        ).decode("utf-8")
        self.verifactu_qr = qr_base64

        # 7. Envolver en sobre SOAP
        soap_envelope = VerifactuEnvelopeBuilderAnulacion(self, config=config).build(
            signed_xml
        )
        self.verifactu_soap_xml = base64.b64encode(soap_envelope.encode("utf-8"))
        
        # 🔁 Nuevo paso 8: Adjuntar el XML **ya envuelto en SOAP**
        xml_attachment = VerifactuAttachmentService(self).attach_xml(soap_envelope)

        # 8. Enviar el XML
        VerifactuSender(self).send(soap_envelope, xml_attachment)

        # 9. Log final
        if self.verifactu_status == "sent":
            builder = VerifactuXMLBuilderAnulacion(self, config)
            VerifactuLogger(self).log("✅ Factura VeriFactu anulada correctamente")
            verifactu_status= "canceled"
        elif self.verifactu_status == "accepted_with_errors":
            builder = VerifactuXMLBuilderAnulacion(self, config)
            VerifactuLogger(self).log(
                "✅ Factura VeriFactu anulada correctamente con errores"
            )
            verifactu_status= "canceled"
        elif self.verifactu_status == "rejected":
            builder = VerifactuXMLBuilderAnulacion(self, config, rechazo_previo=True)
            VerifactuLogger(self).log(
                "🛑 ESte VeriFactu XML de anulacion ha sido rechazado, mira la ventana de error"
            )
        elif self.verifactu_status == "error":
            builder = VerifactuXMLBuilderAnulacion(self, config, rechazo_previo=True)
            VerifactuLogger(self).log(
                "🛑 Error al anular la factura verifactu por favor revisa el error detallado"
            )
        else:
            builder = VerifactuXMLBuilderAnulacion(self, config)
            VerifactuLogger(self).log("✅ Factura VeriFactu anulada correctamente")
            verifactu_status= "canceled"
        return True

    def _validate_before_generation(self):
        if self.state != "posted":
            raise UserError(_("🛑 Intento de procesar factura no confirmada."))

        if self.move_type not in ("out_invoice", "out_refund"):
            raise UserError(
                _("🛑 Solo se pueden procesar facturas de cliente o rectificativas.")
            )

    def _ensure_verifactu_hash(self):
        config = self.env["verifactu.endpoint.config"].sudo().search([
    ('company_id', '=', self.env.company.id)
], limit=1)
        if self.move_type == "out_refund" or not self.verifactu_hash:
            self.verifactu_hash = VerifactuHashCalculator(self,config).compute_hash(
                force_recalculate=True
            )

    def build_verifactu_xml(self):
        return VerifactuXMLBuilder(self).build()

    def _attach_signed_verifactu_xml(self, signed_xml):
        attachment = self.env["ir.attachment"].create(
            {
                "name": f"verifactu_{self.name.replace('/', '_')}.xml",
                "type": "binary",
                "res_model": "account.move",
                "res_id": self.id,
                "datas": base64.b64encode(signed_xml.encode("utf-8")),
                "mimetype": "application/xml",
            }
        )
        return attachment

    def send_verifactu(self, signed_xml_str, attachment):
        return VerifactuSender(self).send(signed_xml_str, attachment)

    def view_verifactu_error(self):
        raise UserError(
            _(
                self.verifactu_detailed_error_msg
                or _("No hay mensaje de error detallado registrado.")
            )
        )

    def resend_verifactu(self):
        return VerifactuResender(self).resend()

    def open_verifactu_xml(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/verifactu/download/{self.id}",
            "target": "new",
        }

    def open_verifactu_soap_xml(self):
        self.ensure_one()
        if not self.verifactu_soap_xml:
            raise UserError(_("El archivo SOAP no está disponible."))

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{self._name}/{self.id}/verifactu_soap_xml/soap_envelope.xml?download=true",
            "target": "new",
        }

    def open_verifactu_qr(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/verifactu/download_qr/{self.id}",
            "target": "new",
        }

    def _get_system_info(self):
        # Datos del sistema informático
        system_name = platform.node()
        system_id = hashlib.sha256(socket.gethostname().encode("utf-8")).hexdigest()[:8]
        system_version = platform.version()
        installation_id = hashlib.sha256(
            (system_name + system_id).encode("utf-8")
        ).hexdigest()[:8]
        multi_ot = "S" if len(self.env["res.company"].sudo().search([])) > 1 else "N"

        return {
            "NombreSistemaInformatico": system_name,
            "IdSistemaInformatico": system_id,
            "Version": system_version,
            "NumeroInstalacion": installation_id,
            "TipoUsoPosibleSoloVerifactu": "S",
            "TipoUsoPosibleOtros": "N",
            "TipoUsoPosibleMultiOT": multi_ot,
        }

    def _is_valid_nif(self, nif):
        """Valida que el NIF tenga un formato básico correcto (8–9 caracteres alfanuméricos)"""
        return bool(re.match(r"^[A-Z0-9]{8,9}$", nif or ""))

    def _validate_verifactu_tax_rates(self):
        valid_tax_rates = {"0", "4", "5", "7", "10", "21"}

        for line in self.invoice_line_ids:
            for tax in line.tax_ids:
                rate_str = str(int(round(tax.amount)))
                if rate_str not in valid_tax_rates:
                    raise UserError(
                        _(
                            "Tipo de IVA no válido para VeriFactu: %s%% en el producto '%s'. "
                            "Solo se permiten los tipos: %s."
                        )
                        % (rate_str, line.name, ", ".join(sorted(valid_tax_rates)))
                    )