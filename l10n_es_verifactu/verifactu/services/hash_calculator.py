import hashlib
from datetime import datetime, timezone
from odoo.fields import Datetime
from odoo import models, fields, api
from odoo.tools import format_datetime

import logging
from ..utils.invoice_type_resolve import VerifactuTipoFacturaResolver
from ..utils.verifactu_xml_validator import VerifactuXMLValidator  # ✅ usamos el NIF de company_id

logger = logging.getLogger(__name__)

# Para más información sobre el hash de VeriFactu consultar la documentación oficial de AEAT
# https://www.agenciatributaria.es/static_files/AEAT_Desarrolladores/EEDD/IVA/VERI-FACTU/Veri-Factu_especificaciones_huella_hash_registros.pdf


class VerifactuHashCalculator:
    def __init__(self, invoice, config):
        self.invoice = invoice
        self.config = config

    # --------------------------------------
    # Huella de Alta (RegistroAlta)
    # --------------------------------------
    def compute_hash(self):
        invoice = self.invoice
        invoice.ensure_one()

        # ✅ Emisor SIEMPRE = company_id (empresa o autónomo)
        company = invoice.company_id
        company_vat_raw = (company.vat or "").strip()
        nif = VerifactuXMLValidator.clean_nif_es(company_vat_raw) if company_vat_raw else ""

        invoice_number = invoice.name.strip() if isinstance(invoice.name, str) else ""
        invoice_date = invoice.invoice_date.strftime("%d-%m-%Y") if invoice.invoice_date else ""
        tipo_factura = VerifactuTipoFacturaResolver.resolve(invoice)
        cuota_total = f"{invoice.amount_tax:.2f}"
        importe_total = f"{invoice.amount_total:.2f}"
        previous_hash = invoice.verifactu_previous_hash or ""

        # 2) Timestamp ISO con huso (utilizamos el ya guardado o ahora)
        timestamp_dt = invoice.verifactu_hash_calculated_at or Datetime.now()
        timestamp_str = timestamp_dt.astimezone().isoformat(timespec="seconds")

        # 3) Cadena base (orden oficial)
        base_string = (
            f"IDEmisorFactura={nif}"
            f"&NumSerieFactura={invoice_number}"
            f"&FechaExpedicionFactura={invoice_date}"
            f"&TipoFactura={tipo_factura}"
            f"&CuotaTotal={cuota_total}"
            f"&ImporteTotal={importe_total}"
            f"&Huella={previous_hash}"
            f"&FechaHoraHusoGenRegistro={timestamp_str}"
        )
        logger.info(f"[VeriFactu] Base para hash (alta): {base_string}")

        return hashlib.sha256(base_string.encode("utf-8")).hexdigest().upper()

    def compute_and_update(self, force_recalculate=False):
        invoice = self.invoice
        invoice.ensure_one()

        # ✅ Asegurar fecha
        if not invoice.invoice_date:
            invoice.invoice_date = fields.Date.today()
            invoice.message_post(body="⚠️ Fecha de factura no definida. Se ha asignado la fecha de hoy.")

        # ✅ Buscar la factura anterior solo si aún no tiene hash previo
        if not invoice.verifactu_previous_hash:
            previous_invoice = invoice.env["account.move"].search(
                [
                    ("invoice_date", "<=", invoice.invoice_date),
                    ("id", "<", invoice.id),
                    ("move_type", "in", ("out_invoice", "out_refund")),
                    ("verifactu_hash", "!=", ""),
                    ("verifactu_date_sent", "!=", False),
                ],
                order="invoice_date desc, id desc",
                limit=1,
            )
            if previous_invoice:
                invoice.verifactu_previous_hash = previous_invoice.verifactu_hash
                invoice.message_post(body=f"🔗 Hash anterior asignado: {previous_invoice.verifactu_hash[:16]}")
            else:
                invoice.message_post(body="⚠️ No se ha encontrado factura anterior con hash válido.")

        # ✅ Timestamp de cálculo del hash
        if not invoice.verifactu_hash_calculated_at or force_recalculate:
            now = fields.Datetime.now()
            invoice.verifactu_hash_calculated_at = now
            invoice.message_post(body=f"🕓 Timestamp fijado para cálculo de hash: {format_datetime(invoice.env, now)}")

        # ✅ Calcular hash
        new_hash = self.compute_hash()
        current_hash = invoice.verifactu_hash

        if force_recalculate or not current_hash or current_hash != new_hash:
            invoice.verifactu_hash = new_hash
            invoice.message_post(body=f"✅ Hash actualizado: {new_hash[:16]}")
        else:
            invoice.message_post(body=f"ℹ️ Hash ya era correcto: {current_hash[:16]}")

        return new_hash

    # --------------------------------------
    # Huella de Anulación (RegistroAnulacion)
    # --------------------------------------
    def compute_cancellation_hash(self):
        invoice = self.invoice
        invoice.ensure_one()

        # ✅ Emisor SIEMPRE = company_id (empresa o autónomo)
        company = invoice.company_id
        company_vat_raw = (company.vat or "").strip()
        nif = VerifactuXMLValidator.clean_nif_es(company_vat_raw) if company_vat_raw else ""

        # ✅ Asegurar huella previa si no está ya establecida
        if not invoice.verifactu_previous_hash:
            previous_invoice = invoice.env["account.move"].search(
                [
                    ("invoice_date", "<", invoice.invoice_date),
                    ("move_type", "in", ("out_invoice", "out_refund")),
                    ("verifactu_hash", "!=", ""),
                    ("verifactu_date_sent", "!=", False),
                ],
                order="invoice_date desc, id desc",
                limit=1,
            )
            if previous_invoice:
                invoice.verifactu_previous_hash = previous_invoice.verifactu_hash
                invoice.message_post(body=f"🔗 Hash anterior asignado automáticamente: {previous_invoice.verifactu_hash[:16]}")
            else:
                invoice.message_post(body="⚠️ No se ha encontrado factura anterior con hash válido.")

        # 1) Datos básicos
        invoice_number = invoice.name.strip() if isinstance(invoice.name, str) else ""
        invoice_date = invoice.invoice_date.strftime("%d-%m-%Y") if invoice.invoice_date else ""

        # 2) Huella anterior (la que se informó en el alta)
        previous_hash = invoice.verifactu_previous_hash or ""

        # 3) Timestamp ISO con huso
        timestamp_dt = invoice.verifactu_hash_calculated_at or fields.Datetime.now()
        timestamp_str = timestamp_dt.astimezone().isoformat(timespec="seconds")

        # 4) Cadena para anulación (orden oficial)
        base_string = (
            f"IDEmisorFacturaAnulada={nif}"
            f"&NumSerieFacturaAnulada={invoice_number}"
            f"&FechaExpedicionFacturaAnulada={invoice_date}"
            f"&Huella={previous_hash}"
            f"&FechaHoraHusoGenRegistro={timestamp_str}"
        )
        logger.info(f"[VeriFactu] Base para hash (anulación): {base_string}")

        return hashlib.sha256(base_string.encode("utf-8")).hexdigest().upper()
