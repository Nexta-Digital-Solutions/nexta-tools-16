# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from itertools import groupby
import logging

from lxml import etree as LET
from odoo.exceptions import UserError

from ...utils.system_info_builder import VerifactuSystemInfoBuilder
from ...utils.invoice_type_resolve import VerifactuTipoFacturaResolver
from ...utils.regime_key import VerifactuRegimeKey
from ...utils.calificacion_operacion import VerifactuOperacionClassifier
from ...services.xml_signer import VerifactuXMLSigner
from ...utils.verifactu_xml_validator import VerifactuXMLValidator

_logger = logging.getLogger(__name__)

NS_SUM  = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroLR.xsd"
NS_SUM1 = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"


class VerifactuXMLBuilderSubsanacion(object):
    """
    Compatible con Odoo 11 → 18:
    - account.invoice (v11–12) y account.move (v13+)
    - number/name, date_invoice/invoice_date
    - invoice_line_tax_ids/tax_ids
    - date_invoice_operation ausente → fallback a fecha de expedición
    """

    def __init__(self, invoice, config, rechazo_previo=False):
        self.invoice = invoice
        self.config = config
        self.rechazo_previo = rechazo_previo

    # ---- Compat helpers -----------------------------------------------------

    def _get_invoice_number(self, inv):
        # v11–12: number ; v13+: name
        return (getattr(inv, "number", None) or getattr(inv, "name", "") or "").strip()

    def _get_invoice_date(self, inv):
        # v11–12: date_invoice (str o date) ; v13+: invoice_date (date)
        if hasattr(inv, "date_invoice") and inv.date_invoice:
            return self._coerce_date(inv.date_invoice)
        if hasattr(inv, "invoice_date") and inv.invoice_date:
            return self._coerce_date(inv.invoice_date)
        # último recurso: date si existe
        if hasattr(inv, "date") and inv.date:
            return self._coerce_date(inv.date)
        return None

    def _get_operation_date(self, inv):
        # Algunos modelos personalizados usan date_invoice_operation
        val = getattr(inv, "date_invoice_operation", None)
        if val:
            return self._coerce_date(val)
        # Fallback: misma fecha que expedición
        return self._get_invoice_date(inv)

    def _get_lines(self, inv):
        # v11–18: invoice_line_ids existe en ambos (account.invoice.line vs account.move.line)
        return list(getattr(inv, "invoice_line_ids", []))

    def _get_line_taxes(self, line):
        # v11–12: invoice_line_tax_ids ; v13+: tax_ids
        taxes = getattr(line, "invoice_line_tax_ids", None)
        if taxes is None:
            taxes = getattr(line, "tax_ids", [])
        return list(taxes)

    def _get_line_subtotal(self, line):
        # v11–18: price_subtotal existe
        return float(getattr(line, "price_subtotal", 0.0) or 0.0)

    def _get_amount_total(self, inv):
        return float(getattr(inv, "amount_total", 0.0) or 0.0)

    def _get_amount_tax(self, inv):
        return float(getattr(inv, "amount_tax", 0.0) or 0.0)

    def _coerce_date(self, val):
        # Admite date/datetime/str (YYYY-MM-DD)
        try:
            from datetime import date, datetime as dt
            if isinstance(val, dt):
                return val.date()
            if hasattr(val, "isoformat"):
                return val  # date
            if isinstance(val, basestring) if "basestring" in dir(__builtins__) else isinstance(val, str):
                # Odoo 11 puede dar str
                return datetime.strptime(val[:10], "%Y-%m-%d").date()
        except Exception:
            pass
        return None

    def _format_date(self, dateobj):
        return dateobj.strftime("%d-%m-%Y") if dateobj else ""

    # ---- Build --------------------------------------------------------------

    def build(self):
        inv = self.invoice
        company = inv.company_id

        # Emisor
        company_vat_raw = (company.vat or "").strip()
        company_vat = VerifactuXMLValidator.clean_nif_es(company_vat_raw) if company_vat_raw else ""
        company_name = (company.name or "").strip()
        if not company_vat or not company_name:
            raise UserError("VeriFactu: faltan datos del emisor en la compañía (VAT/NIF y/o nombre).")

        invoice_number = self._get_invoice_number(inv) or ""
        date_invoice_dt = self._get_invoice_date(inv)
        date_invoice = self._format_date(date_invoice_dt)
        client_name = inv.partner_id.name or "SINNOMBRE"
        client_vat = inv.partner_id.vat or "SINNIF"
        current_hash = getattr(inv, "verifactu_hash", "") or ""
        previous_hash = getattr(inv, "verifactu_previous_hash", "") or "SINHUELLA"

        clave_regimen = VerifactuRegimeKey.compute_clave_regimen(inv)
        calif_operacion_global = VerifactuOperacionClassifier.compute(inv)
        date_operation_dt = self._get_operation_date(inv)
        invpoice_date_operation = self._format_date(date_operation_dt)

        RE_TYPES = {Decimal("5.2"), Decimal("1.4"), Decimal("0.5")}
        base_coste_total = getattr(inv, "verifactu_base_coste", 0.0) or 0.0

        # Root
        registro_factura = ET.Element(ET.QName(NS_SUM, "RegistroFactura"))

        # Nodo firmable
        registro_alta = ET.Element(ET.QName(NS_SUM1, "RegistroAlta"))
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "IDVersion")).text = "1.0"

        id_factura = ET.SubElement(registro_alta, ET.QName(NS_SUM1, "IDFactura"))
        ET.SubElement(id_factura, ET.QName(NS_SUM1, "IDEmisorFactura")).text = company_vat
        ET.SubElement(id_factura, ET.QName(NS_SUM1, "NumSerieFactura")).text = invoice_number
        ET.SubElement(id_factura, ET.QName(NS_SUM1, "FechaExpedicionFactura")).text = date_invoice

        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "NombreRazonEmisor")).text = company_name
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "Subsanacion")).text = "S"
        if self.rechazo_previo:
            ET.SubElement(registro_alta, ET.QName(NS_SUM1, "RechazoPrevio")).text = "S"

        tipo_factura = VerifactuTipoFacturaResolver.resolve(inv)
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "TipoFactura")).text = tipo_factura

        # Rectificativas
        if tipo_factura in ("F4", "R1", "R2", "R3", "R4"):
            tipo_rectificativa = VerifactuXMLValidator.infer_tipo_rectificativa(inv)
            ET.SubElement(registro_alta, ET.QName(NS_SUM1, "TipoRectificativa")).text = tipo_rectificativa

            original = VerifactuXMLValidator.get_original_invoice(inv)

            if original:
                datos_factura = ET.SubElement(registro_alta, ET.QName(NS_SUM1, "DatosFacturaRectificada"))
                ET.SubElement(datos_factura, ET.QName(NS_SUM1, "IDEmisorFactura")).text = company_vat
                num_orig, date_orig = VerifactuXMLValidator.get_original_num_and_date(original)
                ET.SubElement(datos_factura, ET.QName(NS_SUM1, "NumSerieFactura")).text = (num_orig or "DESCONOCIDO")
                ET.SubElement(datos_factura, ET.QName(NS_SUM1, "FechaExpedicionFactura")).text = (
                    self._format_date(date_orig) or "01-01-1900"
                )

            base_rect, cuota_rect = VerifactuXMLValidator.compute_importe_rectificacion(
                inv, original, tipo_rectificativa
            )
            importe = ET.SubElement(registro_alta, ET.QName(NS_SUM1, "ImporteRectificacion"))
            ET.SubElement(importe, ET.QName(NS_SUM1, "BaseRectificada")).text = "%.2f" % (base_rect,)
            ET.SubElement(importe, ET.QName(NS_SUM1, "CuotaRectificada")).text = "%.2f" % (cuota_rect,)

        descripcion_operacion = VerifactuXMLValidator.build_descripcion_operacion(inv)
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "DescripcionOperacion")).text = descripcion_operacion

        # Destinatario
        if tipo_factura in ("F2", "R5"):
            vat = (inv.partner_id.vat or "").upper().strip()
            if not vat or vat == "SINNIF":
                ET.SubElement(registro_alta, ET.QName(NS_SUM1, "FacturaSinIdentifDestinatarioArt61d")).text = "S"
        else:
            destinatarios = ET.SubElement(registro_alta, ET.QName(NS_SUM1, "Destinatarios"))
            id_dest = ET.SubElement(destinatarios, ET.QName(NS_SUM1, "IDDestinatario"))
            ET.SubElement(id_dest, ET.QName(NS_SUM1, "NombreRazon")).text = client_name
            ET.SubElement(id_dest, ET.QName(NS_SUM1, "NIF")).text = VerifactuXMLValidator.clean_nif_es(client_vat)

        # --- Desglose ---
        desglose = ET.SubElement(registro_alta, ET.QName(NS_SUM1, "Desglose"))
        clave_regimen = VerifactuRegimeKey.compute_clave_regimen(inv)

        # Con impuestos
        line_items = []
        for line in self._get_lines(inv):
            calificacion = VerifactuOperacionClassifier.compute_from_line(line)
            for tax in self._get_line_taxes(line):
                line_items.append({
                    "tax": tax,
                    "base": self._get_line_subtotal(line),
                    "calificacion": calificacion,
                })

        line_items.sort(key=lambda x: (x["tax"].id, x["calificacion"]))
        for (tax, calificacion), group in groupby(line_items, key=lambda x: (x["tax"], x["calificacion"])):
            group_list = list(group)
            base_total = sum(item["base"] for item in group_list)

            detalle = ET.SubElement(desglose, ET.QName(NS_SUM1, "DetalleDesglose"))
            ET.SubElement(detalle, ET.QName(NS_SUM1, "ClaveRegimen")).text = clave_regimen
            ET.SubElement(detalle, ET.QName(NS_SUM1, "CalificacionOperacion")).text = calificacion

            if calificacion == "S2":
                ET.SubElement(detalle, ET.QName(NS_SUM1, "OperacionExenta")).text = "E1"

            # En no-sujetas N1/N2 no poner tipo/cuota
            if calificacion not in ["N1", "N2"]:
                tipo_impositivo = Decimal(str(getattr(tax, "amount", 0.0))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                ET.SubElement(detalle, ET.QName(NS_SUM1, "TipoImpositivo")).text = str(tipo_impositivo)

            ET.SubElement(detalle, ET.QName(NS_SUM1, "BaseImponibleOimporteNoSujeto")).text = f"{base_total:.2f}"

            if tipo_factura in ("F2", "F3", "R5") and clave_regimen == "06":
                base_coste_proporcional = VerifactuXMLValidator.compute_base_coste_proporcional(
                    inv, base_total, base_coste_total
                )
                ET.SubElement(detalle, ET.QName(NS_SUM1, "BaseImponibleACoste")).text = f"{Decimal(base_coste_proporcional).quantize(Decimal('0.01'))}"

            if calificacion not in ["N1", "N2"]:
                cuota = Decimal(base_total) * Decimal(str(getattr(tax, "amount", 0.0))) / Decimal("100")
                cuota = cuota.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                ET.SubElement(detalle, ET.QName(NS_SUM1, "CuotaRepercutida")).text = str(cuota)

            # Recargo equivalencia si el % coincide
            try:
                tax_pct = Decimal(str(getattr(tax, "amount", 0.0))).quantize(Decimal("0.01"))
            except Exception:
                tax_pct = Decimal("0.00")
            if tax_pct in RE_TYPES:
                ET.SubElement(detalle, ET.QName(NS_SUM1, "TipoRecargoEquivalencia")).text = str(tax_pct)
                cuota_recargo = (Decimal(base_total) * tax_pct / Decimal("100")).quantize(Decimal("0.01"))
                ET.SubElement(detalle, ET.QName(NS_SUM1, "CuotaRecargoEquivalencia")).text = str(cuota_recargo)

        # Sin impuestos
        line_items_no_tax = []
        for line in self._get_lines(inv):
            if not self._get_line_taxes(line):
                line_items_no_tax.append({
                    "base": self._get_line_subtotal(line),
                    "calificacion": VerifactuOperacionClassifier.compute_from_line(line),
                })

        for calificacion, group in groupby(
            sorted(line_items_no_tax, key=lambda x: x["calificacion"]),
            key=lambda x: x["calificacion"]
        ):
            group_list = list(group)
            base_total = sum(item["base"] for item in group_list)

            detalle = ET.SubElement(desglose, ET.QName(NS_SUM1, "DetalleDesglose"))
            ET.SubElement(detalle, ET.QName(NS_SUM1, "ClaveRegimen")).text = clave_regimen
            ET.SubElement(detalle, ET.QName(NS_SUM1, "CalificacionOperacion")).text = calificacion
            if calificacion == "S2":
                ET.SubElement(detalle, ET.QName(NS_SUM1, "OperacionExenta")).text = "E1"
            ET.SubElement(detalle, ET.QName(NS_SUM1, "BaseImponibleOimporteNoSujeto")).text = f"{base_total:.2f}"
            if calificacion not in ["N1", "N2"]:
                ET.SubElement(detalle, ET.QName(NS_SUM1, "TipoImpositivo")).text = "0.00"
                ET.SubElement(detalle, ET.QName(NS_SUM1, "CuotaRepercutida")).text = "0.00"

        # Totales
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "CuotaTotal")).text = f"{self._get_amount_tax(inv):.2f}"
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "ImporteTotal")).text = f"{self._get_amount_total(inv):.2f}"

        # Encadenamiento
        encadenamiento = ET.SubElement(registro_alta, ET.QName(NS_SUM1, "Encadenamiento"))
        anterior = ET.SubElement(encadenamiento, ET.QName(NS_SUM1, "RegistroAnterior"))
        ET.SubElement(anterior, ET.QName(NS_SUM1, "IDEmisorFactura")).text = company_vat
        ET.SubElement(anterior, ET.QName(NS_SUM1, "NumSerieFactura")).text = invoice_number
        ET.SubElement(anterior, ET.QName(NS_SUM1, "FechaExpedicionFactura")).text = date_invoice
        ET.SubElement(anterior, ET.QName(NS_SUM1, "Huella")).text = previous_hash

        # Info sistema
        VerifactuSystemInfoBuilder(inv.company_id, self.config).append_to(registro_alta)

        # Sello y huella
        now = datetime.now().astimezone()
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "FechaHoraHusoGenRegistro")).text = now.isoformat(timespec='seconds')
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "TipoHuella")).text = "01"
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "Huella")).text = current_hash

        # Firma de RegistroAlta
        raw_alta = ET.tostring(registro_alta, encoding="utf-8")
        signed_str = VerifactuXMLSigner(self.config).sign(raw_alta)
        signed_lxml = LET.fromstring(signed_str)
        signed_etree = ET.fromstring(LET.tostring(signed_lxml))

        registro_factura.append(signed_etree)

        return minidom.parseString(ET.tostring(registro_factura)).toprettyxml(indent="  ")
