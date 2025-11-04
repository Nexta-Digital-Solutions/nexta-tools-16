# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from lxml import etree as LET
from odoo.exceptions import UserError

from ...utils.system_info_builder import VerifactuSystemInfoBuilder
from ...services.xml_signer import VerifactuXMLSigner
from ...utils.verifactu_xml_validator import VerifactuXMLValidator

NS_SUM  = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroLR.xsd"
NS_SUM1 = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"


class VerifactuXMLBuilderAnulacion(object):
    """
    Compatible con Odoo 11 → 18:
    - account.invoice (v11–12) y account.move (v13+)
    - number/name, date_invoice/invoice_date
    - previous_hash vacío → 'SINHUELLA'
    - añade atributo Id al nodo firmado y permite reference_uri en el signer
    """

    def __init__(self, invoice, config, rechazo_previo=False, sin_Factura_anterior=False):
        self.invoice = invoice
        self.config = config
        self.rechazo_previo = rechazo_previo
        self.sin_Factura_anterior = sin_Factura_anterior

    # ---------------- Compat helpers ----------------

    def _get_invoice_number(self, inv):
        # v11–12: number ; v13+: name
        return (getattr(inv, "number", None) or getattr(inv, "name", "") or "").strip()

    def _coerce_date(self, val):
        # Admite date/datetime/str 'YYYY-MM-DD'
        try:
            from datetime import date as ddate, datetime as ddt
            if isinstance(val, ddt):
                return val.date()
            if hasattr(val, "isoformat") and not isinstance(val, str):
                return val  # date
            if isinstance(val, str):
                return datetime.strptime(val[:10], "%Y-%m-%d").date()
        except Exception:
            pass
        return None

    def _get_invoice_date(self, inv):
        # v11–12: date_invoice ; v13+: invoice_date ; fallback: date
        if getattr(inv, "date_invoice", None):
            return self._coerce_date(inv.date_invoice)
        if getattr(inv, "invoice_date", None):
            return self._coerce_date(inv.invoice_date)
        if getattr(inv, "date", None):
            return self._coerce_date(inv.date)
        return None

    def _format_ddmmyyyy(self, d):
        return d.strftime("%d-%m-%Y") if d else ""

    def _get_current_hash(self, inv):
        return (getattr(inv, "verifactu_hash", "") or "").strip()

    def _get_previous_hash(self, inv):
        return (getattr(inv, "verifactu_previous_hash", "") or "") or "SINHUELLA"

    # ---------------- Build ----------------

    def build(self):
        inv = self.invoice
        company = inv.company_id

        # Emisor = compañía
        emisor_nif = VerifactuXMLValidator.clean_nif_es((company.vat or "").strip()) if company.vat else ""
        if not emisor_nif:
            raise UserError("VeriFactu: la compañía no tiene NIF/CIF configurado.")

        invoice_number = self._get_invoice_number(inv)
        date_invoice_str = self._format_ddmmyyyy(self._get_invoice_date(inv))
        current_hash = self._get_current_hash(inv)
        previous_hash = self._get_previous_hash(inv)

        # Nodo firmado: <RegistroAnulacion>
        registro_anulacion = ET.Element(ET.QName(NS_SUM1, "RegistroAnulacion"))
        ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "IDVersion")).text = "1.0"

        id_factura = ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "IDFactura"))
        ET.SubElement(id_factura, ET.QName(NS_SUM1, "IDEmisorFacturaAnulada")).text = emisor_nif
        ET.SubElement(id_factura, ET.QName(NS_SUM1, "NumSerieFacturaAnulada")).text = invoice_number
        ET.SubElement(id_factura, ET.QName(NS_SUM1, "FechaExpedicionFacturaAnulada")).text = date_invoice_str

        # Rechazo previo vs Sin registro previo (mutuamente excluyentes)
        if self.rechazo_previo:
            ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "RechazoPrevio")).text = "S"
        elif self.sin_Factura_anterior:
            ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "SinRegistroPrevio")).text = "S"

        # Encadenamiento
        encadenamiento = ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "Encadenamiento"))
        anterior = ET.SubElement(encadenamiento, ET.QName(NS_SUM1, "RegistroAnterior"))
        ET.SubElement(anterior, ET.QName(NS_SUM1, "IDEmisorFactura")).text = emisor_nif
        ET.SubElement(anterior, ET.QName(NS_SUM1, "NumSerieFactura")).text = invoice_number
        ET.SubElement(anterior, ET.QName(NS_SUM1, "FechaExpedicionFactura")).text = date_invoice_str
        ET.SubElement(anterior, ET.QName(NS_SUM1, "Huella")).text = previous_hash

        # Sistema informático
        VerifactuSystemInfoBuilder(inv.company_id, self.config).append_to(registro_anulacion)

        # Sello tiempo + huella actual
        now = datetime.now().astimezone()
        ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "FechaHoraHusoGenRegistro")).text = now.isoformat(timespec='seconds')
        ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "TipoHuella")).text = "01"
        ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "Huella")).text = current_hash

        # --- Id del elemento firmado + firma ---
        unique_id = f"ANU-{(invoice_number or 's/n').replace('/', '-')}"
        registro_anulacion.set("Id", unique_id)

        raw_anulacion = ET.tostring(registro_anulacion, encoding="utf-8")

        signer = VerifactuXMLSigner(self.config)
        try:
            # si tu signer acepta reference_uri, úsalo
            signed_str = signer.sign(raw_anulacion, reference_uri=f"#{unique_id}")
        except TypeError:
            # fallback: firma sin pasar URI (tu signer deberá ponerla)
            signed_str = signer.sign(raw_anulacion)

        signed_lxml = LET.fromstring(signed_str)
        signed_etree = ET.fromstring(LET.tostring(signed_lxml))

        # Envolver dentro de <RegistroFactura>
        registro_factura = ET.Element(ET.QName(NS_SUM, "RegistroFactura"))
        registro_factura.append(signed_etree)

        return minidom.parseString(ET.tostring(registro_factura)).toprettyxml(indent="  ")
