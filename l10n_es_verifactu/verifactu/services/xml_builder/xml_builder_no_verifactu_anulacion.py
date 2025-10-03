# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from lxml import etree as LET
from odoo.exceptions import UserError

from ...utils.system_info_builder import VerifactuSystemInfoBuilder
from ...services.xml_signer import VerifactuXMLSigner
from ...utils.verifactu_xml_validator import VerifactuXMLValidator

NS_SOAPENV = "http://schemas.xmlsoap.org/soap/envelope/"
NS_SUM     = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroLR.xsd"
NS_SUM1    = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"


class VerifactuXMLBuilderNoVerifactuAnulacion(object):
    """
    Builder compatible Odoo 11 → 18.
    - number/name
    - invoice_date/date_invoice/date
    - previous_hash vacío → 'SINHUELLA'
    - firma mantenida sin reference_uri (como pediste)
    """

    def __init__(self, invoice, config, rechazo_previo=False, sin_Factura_anterior=False):
        self.invoice = invoice
        self.config = config
        self.rechazo_previo = rechazo_previo
        self.sin_Factura_anterior = sin_Factura_anterior

    # -------- Helpers de compat --------
    def _inv_number(self, inv):
        # v11–12: number ; v13+: name
        return (getattr(inv, "name", None) or getattr(inv, "number", "") or "").strip()

    def _coerce_date(self, val):
        try:
            from datetime import datetime as ddt
            if isinstance(val, ddt):
                return val.date()
            if hasattr(val, "isoformat") and not isinstance(val, str):  # date
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

    def _current_hash(self, inv):
        return (getattr(inv, "verifactu_hash", "") or "").strip()

    def _previous_hash(self, inv):
        return (getattr(inv, "verifactu_previous_hash", "") or "") or "SINHUELLA"

    # -------- Build --------
    def build(self):
        inv = self.invoice
        company = inv.company_id

        # Emisor desde company_id
        company_name = (company.name or "").strip()
        company_vat_raw = (company.vat or "").strip()
        emisor_nif = VerifactuXMLValidator.clean_nif_es(company_vat_raw) if company_vat_raw else ""
        if not company_name or not emisor_nif:
            raise UserError("VeriFactu: faltan datos del emisor en la compañía (Nombre y/o NIF/CIF).")

        invoice_number = self._inv_number(inv)
        invoice_date   = self._fmt_ddmmyyyy(self._inv_date(inv))
        previous_hash  = self._previous_hash(inv)
        current_hash   = self._current_hash(inv)
        verifactu_requerimiento = getattr(inv, "verifactu_requerimiento", "") or ""

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
        ET.SubElement(obligado, ET.QName(NS_SUM1, "NIF")).text = emisor_nif

        # Remisión por requerimiento (No VeriFactu)
        remision = ET.SubElement(cabecera, ET.QName(NS_SUM1, "RemisionRequerimiento"))
        ET.SubElement(remision, ET.QName(NS_SUM1, "RefRequerimiento")).text = verifactu_requerimiento

        registro_factura = ET.SubElement(reg_factu, ET.QName(NS_SUM, "RegistroFactura"))

        # Nodo firmable: RegistroAnulacion
        registro_anulacion = ET.Element(ET.QName(NS_SUM1, "RegistroAnulacion"))
        ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "IDVersion")).text = "1.0"

        id_factura = ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "IDFactura"))
        ET.SubElement(id_factura, ET.QName(NS_SUM1, "IDEmisorFacturaAnulada")).text = emisor_nif
        ET.SubElement(id_factura, ET.QName(NS_SUM1, "NumSerieFacturaAnulada")).text = invoice_number
        ET.SubElement(id_factura, ET.QName(NS_SUM1, "FechaExpedicionFacturaAnulada")).text = invoice_date

        # Encadenamiento
        encadenamiento = ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "Encadenamiento"))
        anterior = ET.SubElement(encadenamiento, ET.QName(NS_SUM1, "RegistroAnterior"))
        ET.SubElement(anterior, ET.QName(NS_SUM1, "IDEmisorFactura")).text = emisor_nif
        ET.SubElement(anterior, ET.QName(NS_SUM1, "NumSerieFactura")).text = invoice_number
        ET.SubElement(anterior, ET.QName(NS_SUM1, "FechaExpedicionFactura")).text = invoice_date
        ET.SubElement(anterior, ET.QName(NS_SUM1, "Huella")).text = previous_hash

        # Sello tiempo + huella actual
        now = datetime.now().astimezone()
        ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "FechaHoraHusoGenRegistro")).text = now.isoformat(timespec="seconds")
        ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "TipoHuella")).text = "01"
        ET.SubElement(registro_anulacion, ET.QName(NS_SUM1, "Huella")).text = current_hash

        # Firma (dejamos tu signer tal cual)
        raw_anulacion = ET.tostring(registro_anulacion, encoding="utf-8")
        signed_str = VerifactuXMLSigner(self.config).sign(raw_anulacion)
        signed_lxml = LET.fromstring(signed_str)
        signed_etree = ET.fromstring(LET.tostring(signed_lxml))

        # Insertar firmado en RegistroFactura
        registro_factura.append(signed_etree)

        return minidom.parseString(ET.tostring(envelope)).toprettyxml(indent="  ")
