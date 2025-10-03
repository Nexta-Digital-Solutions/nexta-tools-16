# Desarrollado por Juan Ormaechea (Mr. Rubik) — Todos los derechos reservados
# Este módulo está protegido por la Odoo Proprietary License v1.0
# Cualquier redistribución está prohibida sin autorización expresa.

import xml.etree.ElementTree as ET
from odoo.exceptions import UserError
from ..utils.verifactu_xml_validator import VerifactuXMLValidator  # ✅ para limpiar NIF

NS_SUM1 = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/SuministroInformacion.xsd"


class VerifactuSystemInfoBuilder:
    def __init__(self, company, config):
        self.company = company
        self.config = config

    def get_system_info(self):
        return {
            "NombreSistemaInformatico": self.config.verifactu_system_name or "VERIFACTU JO Module",
            "IdSistemaInformatico": self.config.verifactu_system_id or "89",
            "Version": self.config.verifactu_system_version or "2.0.1",
            "NumeroInstalacion": self.config.verifactu_system_installation_number or "389",
            "TipoUsoPosibleSoloVerifactu": self.config.verifactu_system_use_only_verifactu or "N",
            "TipoUsoPosibleMultiOT": self.config.verifactu_system_multi_ot or "S",
            "IndicadorMultiplesOT": self.config.verifactu_system_multiple_ot_indicator or "S",
        }

    def append_to(self, parent_element):
        info = self.get_system_info()

        # ✅ Emisor/titular del sistema = compañía (empresa o autónomo)
        company_name = (self.company.name or "").strip()
        company_vat_raw = (self.company.vat or "").strip()
        company_vat = VerifactuXMLValidator.clean_nif_es(company_vat_raw) if company_vat_raw else ""

        if not company_name or not company_vat:
            raise UserError("VeriFactu: faltan datos en la compañía (Nombre y/o NIF/CIF) para 'SistemaInformatico'.")

        sistema = ET.SubElement(parent_element, ET.QName(NS_SUM1, "SistemaInformatico"))
        ET.SubElement(sistema, ET.QName(NS_SUM1, "NombreRazon")).text = company_name
        ET.SubElement(sistema, ET.QName(NS_SUM1, "NIF")).text = company_vat
        ET.SubElement(sistema, ET.QName(NS_SUM1, "NombreSistemaInformatico")).text = info["NombreSistemaInformatico"]
        ET.SubElement(sistema, ET.QName(NS_SUM1, "IdSistemaInformatico")).text = info["IdSistemaInformatico"]
        ET.SubElement(sistema, ET.QName(NS_SUM1, "Version")).text = info["Version"]
        ET.SubElement(sistema, ET.QName(NS_SUM1, "NumeroInstalacion")).text = info["NumeroInstalacion"]
        ET.SubElement(sistema, ET.QName(NS_SUM1, "TipoUsoPosibleSoloVerifactu")).text = info["TipoUsoPosibleSoloVerifactu"]
        ET.SubElement(sistema, ET.QName(NS_SUM1, "TipoUsoPosibleMultiOT")).text = info["TipoUsoPosibleMultiOT"]
        ET.SubElement(sistema, ET.QName(NS_SUM1, "IndicadorMultiplesOT")).text = info["IndicadorMultiplesOT"]
