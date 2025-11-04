# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from itertools import groupby

from lxml import etree as LET
from odoo.exceptions import UserError

from ...utils.system_info_builder import VerifactuSystemInfoBuilder
from ...utils.regime_key import VerifactuRegimeKey
from ...utils.calificacion_operacion import VerifactuOperacionClassifier
from ...utils.invoice_type_resolve import VerifactuTipoFacturaResolver
from ...services.xml_signer import VerifactuXMLSigner
from ...utils.verifactu_xml_validator import VerifactuXMLValidator

NS_SOAPENV = "http://schemas.xmlsoap.org/soap/envelope/"
NS_SUM     = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroLR.xsd"
NS_SUM1    = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"


class VerifactuXMLBuilderNoVerifactu(object):
    """
    Compatible Odoo 11 → 18:
    - account.invoice (v11–12) y account.move (v13+)
    - number/name, date_invoice/invoice_date/date
    - invoice_line_tax_ids/tax_ids
    - previous_hash vacío → 'SINHUELLA'
    - firma con atributo Id opcional (si tu signer soporta reference_uri)
    """

    RE_TYPES = {Decimal("5.2"), Decimal("1.4"), Decimal("0.5")}

    def __init__(self, invoice, config, rechazo_previo=False):
        self.invoice = invoice
        self.config = config
        self.rechazo_previo = rechazo_previo

    # ---------------- Compat helpers ----------------
    def _inv_number(self, inv):
        # v11–12: number ; v13+: name
        return (getattr(inv, "name", None) or getattr(inv, "number", "") or "").strip()

    def _coerce_date(self, val):
        try:
            from datetime import datetime as ddt
            if isinstance(val, ddt):
                return val.date()
            # date tiene .isoformat y no es str
            if hasattr(val, "isoformat") and not isinstance(val, str):
                return val
            if isinstance(val, str):
                return datetime.strptime(val[:10], "%Y-%m-%d").date()
        except Exception:
            pass
        return None

    def _inv_date(self, inv):
        # v11–12: date_invoice ; v13+: invoice_date ; fallback: date
        if getattr(inv, "invoice_date", None):
            return self._coerce_date(inv.invoice_date)
        if getattr(inv, "date_invoice", None):
            return self._coerce_date(inv.date_invoice)
        if getattr(inv, "date", None):
            return self._coerce_date(inv.date)
        return None

    def _fmt_ddmmyyyy(self, d):
        d = VerifactuXMLValidator._to_date(d)
        return d.strftime("%d-%m-%Y") if d else ""

    def _inv_lines(self, inv):
        return list(getattr(inv, "invoice_line_ids", []))

    def _line_taxes(self, line):
        taxes = getattr(line, "tax_ids", None)
        if taxes is None:
            taxes = getattr(line, "invoice_line_tax_ids", [])
        return list(taxes)

    def _line_subtotal(self, line):
        return float(getattr(line, "price_subtotal", 0.0) or 0.0)

    def _tax_percent(self, tax):
        try:
            return Decimal(str(getattr(tax, "amount", 0.0))).quantize(Decimal("0.01"))
        except Exception:
            return Decimal("0.00")

    def _money(self, x):
        return Decimal(str(x or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _current_hash(self, inv):
        return (getattr(inv, "verifactu_hash", "") or "").strip()

    def _previous_hash(self, inv):
        return (getattr(inv, "verifactu_previous_hash", "") or "") or "SINHUELLA"

    # ---------------- Build ----------------
    def build(self):
        inv = self.invoice
        company = inv.company_id

        # Emisor (empresa/autónomo) desde company_id
        company_name = (company.name or "").strip()
        company_vat_raw = (company.vat or "").strip()
        company_vat = VerifactuXMLValidator.clean_nif_es(company_vat_raw) if company_vat_raw else ""
        if not company_name or not company_vat:
            raise UserError("VeriFactu: faltan datos del emisor en la compañía (Nombre y/o NIF/CIF).")

        invoice_number = self._inv_number(inv)
        invoice_date = self._fmt_ddmmyyyy(self._inv_date(inv))
        client_name = inv.partner_id.name or "SINNOMBRE"

        previous_hash = self._previous_hash(inv)
        current_hash = self._current_hash(inv)

        clave_regimen = VerifactuRegimeKey.compute_clave_regimen(inv)
        # calif_operacion_global = VerifactuOperacionClassifier.compute(inv)  # si lo usas en algún texto
        verifactu_requerimiento = getattr(inv, "verifactu_requerimiento", "") or ""
        base_coste_total = getattr(inv, "verifactu_base_coste", 0.0) or 0.0

        # Namespaces
        ET.register_namespace("soapenv", NS_SOAPENV)
        ET.register_namespace("sum", NS_SUM)
        ET.register_namespace("sum1", NS_SUM1)
        ET.register_namespace("xd", "http://www.w3.org/2000/09/xmldsig#")

        # Envelope SOAP
        envelope = ET.Element(ET.QName(NS_SOAPENV, "Envelope"))
        ET.SubElement(envelope, ET.QName(NS_SOAPENV, "Header"))
        body = ET.SubElement(envelope, ET.QName(NS_SOAPENV, "Body"))
        reg_factu = ET.SubElement(body, ET.QName(NS_SUM, "RegFactuSistemaFacturacion"))

        # Cabecera / ObligadoEmision
        cabecera = ET.SubElement(reg_factu, ET.QName(NS_SUM, "Cabecera"))
        obligado = ET.SubElement(cabecera, ET.QName(NS_SUM1, "ObligadoEmision"))
        ET.SubElement(obligado, ET.QName(NS_SUM1, "NombreRazon")).text = company_name
        ET.SubElement(obligado, ET.QName(NS_SUM1, "NIF")).text = company_vat

        # Remisión por requerimiento (No VeriFactu)
        remision = ET.SubElement(cabecera, ET.QName(NS_SUM1, "RemisionRequerimiento"))
        ET.SubElement(remision, ET.QName(NS_SUM1, "RefRequerimiento")).text = verifactu_requerimiento

        # RegistroFactura y RegistroAlta (firmable)
        registro_factura = ET.SubElement(reg_factu, ET.QName(NS_SUM, "RegistroFactura"))
        registro_alta = ET.Element(ET.QName(NS_SUM1, "RegistroAlta"))

        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "IDVersion")).text = "1.0"

        # IDFactura (emisor correcto = company_vat)
        id_factura = ET.SubElement(registro_alta, ET.QName(NS_SUM1, "IDFactura"))
        ET.SubElement(id_factura, ET.QName(NS_SUM1, "IDEmisorFactura")).text = company_vat
        ET.SubElement(id_factura, ET.QName(NS_SUM1, "NumSerieFactura")).text = invoice_number
        ET.SubElement(id_factura, ET.QName(NS_SUM1, "FechaExpedicionFactura")).text = invoice_date

        # Nombre del emisor
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "NombreRazonEmisor")).text = company_name

        # TipoFactura
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
                    self._fmt_ddmmyyyy(date_orig) or "01-01-1900"
                )

            base_rect, cuota_rect = VerifactuXMLValidator.compute_importe_rectificacion(inv, original, tipo_rectificativa)
            importe = ET.SubElement(registro_alta, ET.QName(NS_SUM1, "ImporteRectificacion"))
            ET.SubElement(importe, ET.QName(NS_SUM1, "BaseRectificada")).text = "%.2f" % (base_rect,)
            ET.SubElement(importe, ET.QName(NS_SUM1, "CuotaRectificada")).text = "%.2f" % (cuota_rect,)

        # Descripción
        descripcion_operacion = VerifactuXMLValidator.build_descripcion_operacion(inv)
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "DescripcionOperacion")).text = descripcion_operacion

        # Destinatario / 61.d
        if tipo_factura in ("F2", "R5"):
            vat = (inv.partner_id.vat or "").upper().strip()
            if not vat or vat == "SINNIF":
                ET.SubElement(registro_alta, ET.QName(NS_SUM1, "FacturaSinIdentifDestinatarioArt61d")).text = "S"
        else:
            destinatarios = ET.SubElement(registro_alta, ET.QName(NS_SUM1, "Destinatarios"))
            id_dest = ET.SubElement(destinatarios, ET.QName(NS_SUM1, "IDDestinatario"))
            ET.SubElement(id_dest, ET.QName(NS_SUM1, "NombreRazon")).text = client_name or "SINNOMBRE"

            idinfo = VerifactuXMLValidator.build_id_for_xml(inv.partner_id)
            if idinfo.get("tag") == "NIF":
                ET.SubElement(id_dest, ET.QName(NS_SUM1, "NIF")).text = idinfo.get("value", "")
            else:
                _id = (idinfo.get("ID") or "").strip()
                if not _id:
                    raise UserError("VeriFactu: el destinatario no tiene NIF válido ni ID alternativo (IDType/CodigoPais/ID).")
                idotro = ET.SubElement(id_dest, ET.QName(NS_SUM1, "IDOtro"))
                ET.SubElement(idotro, ET.QName(NS_SUM1, "IDType")).text = idinfo.get("IDType", "")
                ET.SubElement(idotro, ET.QName(NS_SUM1, "CodigoPais")).text = idinfo.get("CodigoPais", "")
                ET.SubElement(idotro, ET.QName(NS_SUM1, "ID")).text = _id

        # --- Desglose ---
        desglose = ET.SubElement(registro_alta, ET.QName(NS_SUM1, "Desglose"))
        clave_regimen = VerifactuRegimeKey.compute_clave_regimen(inv)

        # Con impuestos
        line_items = []
        for line in self._inv_lines(inv):
            calificacion = VerifactuOperacionClassifier.compute_from_line(line)
            for tax in self._line_taxes(line):
                line_items.append({
                    "tax": tax,
                    "base": self._line_subtotal(line),
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

            if calificacion not in ["N1", "N2"]:
                tipo_impositivo = self._tax_percent(tax)
                ET.SubElement(detalle, ET.QName(NS_SUM1, "TipoImpositivo")).text = str(tipo_impositivo)

            ET.SubElement(detalle, ET.QName(NS_SUM1, "BaseImponibleOimporteNoSujeto")).text = f"{self._money(base_total)}"

            if tipo_factura in ("F2", "F3", "R5") and clave_regimen == "06":
                base_coste_proporcional = VerifactuXMLValidator.compute_base_coste_proporcional(inv, base_total, base_coste_total)
                ET.SubElement(detalle, ET.QName(NS_SUM1, "BaseImponibleACoste")).text = f"{self._money(base_coste_proporcional)}"

            if calificacion not in ["N1", "N2"]:
                cuota = (Decimal(base_total) * self._tax_percent(tax) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                ET.SubElement(detalle, ET.QName(NS_SUM1, "CuotaRepercutida")).text = str(cuota)

            tax_pct = self._tax_percent(tax)
            if tax_pct in self.RE_TYPES:
                ET.SubElement(detalle, ET.QName(NS_SUM1, "TipoRecargoEquivalencia")).text = str(tax_pct)
                cuota_recargo = (Decimal(base_total) * tax_pct / Decimal("100")).quantize(Decimal("0.01"))
                ET.SubElement(detalle, ET.QName(NS_SUM1, "CuotaRecargoEquivalencia")).text = str(cuota_recargo)

        # Sin impuestos
        line_items_no_tax = []
        for line in self._inv_lines(inv):
            if not self._line_taxes(line):
                line_items_no_tax.append({
                    "base": self._line_subtotal(line),
                    "calificacion": VerifactuOperacionClassifier.compute_from_line(line),
                })

        for calificacion, group in groupby(sorted(line_items_no_tax, key=lambda x: x["calificacion"]), key=lambda x: x["calificacion"]):
            group_list = list(group)
            base_total = sum(item["base"] for item in group_list)

            detalle = ET.SubElement(desglose, ET.QName(NS_SUM1, "DetalleDesglose"))
            ET.SubElement(detalle, ET.QName(NS_SUM1, "ClaveRegimen")).text = clave_regimen
            ET.SubElement(detalle, ET.QName(NS_SUM1, "CalificacionOperacion")).text = calificacion
            if calificacion == "S2":
                ET.SubElement(detalle, ET.QName(NS_SUM1, "OperacionExenta")).text = "E1"
            ET.SubElement(detalle, ET.QName(NS_SUM1, "BaseImponibleOimporteNoSujeto")).text = f"{self._money(base_total)}"
            if calificacion not in ["N1", "N2"]:
                ET.SubElement(detalle, ET.QName(NS_SUM1, "TipoImpositivo")).text = "0.00"
                ET.SubElement(detalle, ET.QName(NS_SUM1, "CuotaRepercutida")).text = "0.00"

        # Totales
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "CuotaTotal")).text = f"{self._money(getattr(inv, 'amount_tax', 0.0))}"
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "ImporteTotal")).text = f"{self._money(getattr(inv, 'amount_total', 0.0))}"

        # Encadenamiento
        encadenamiento = ET.SubElement(registro_alta, ET.QName(NS_SUM1, "Encadenamiento"))
        anterior = ET.SubElement(encadenamiento, ET.QName(NS_SUM1, "RegistroAnterior"))
        ET.SubElement(anterior, ET.QName(NS_SUM1, "IDEmisorFactura")).text = company_vat
        ET.SubElement(anterior, ET.QName(NS_SUM1, "NumSerieFactura")).text = invoice_number
        ET.SubElement(anterior, ET.QName(NS_SUM1, "FechaExpedicionFactura")).text = invoice_date
        ET.SubElement(anterior, ET.QName(NS_SUM1, "Huella")).text = previous_hash

        # Info del sistema
        VerifactuSystemInfoBuilder(inv.company_id, self.config).append_to(registro_alta)

        # Sello de tiempo y huella actual
        now = datetime.now().astimezone()
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "FechaHoraHusoGenRegistro")).text = now.isoformat(timespec="seconds")
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "TipoHuella")).text = "01"
        ET.SubElement(registro_alta, ET.QName(NS_SUM1, "Huella")).text = current_hash

        # --- Firma del RegistroAlta ---
        # Atributo Id opcional (si tu signer lo usa para Reference URI)
        unique_id = "RA-%s" % (invoice_number.replace("/", "-") or "s-n")
        registro_alta.set("Id", unique_id)

        # Firma de RegistroAlta
        raw_alta = ET.tostring(registro_alta, encoding="utf-8")
        signed_str = VerifactuXMLSigner(self.config).sign(raw_alta)
        signed_lxml = LET.fromstring(signed_str)
        signed_etree = ET.fromstring(LET.tostring(signed_lxml))

        registro_factura.append(signed_etree)

        return minidom.parseString(ET.tostring(envelope)).toprettyxml(indent="  ")
