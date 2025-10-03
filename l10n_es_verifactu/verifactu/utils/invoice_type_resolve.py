class VerifactuTipoFacturaResolver:
    @staticmethod
    def resolve(invoice):
        """
        Determina el tipo de factura VeriFactu a partir de los datos del move.
        """

        # 1. Rectificativas (devoluciones)
        if invoice.move_type == 'out_refund':
            return "R1"  # Rectificativa simplificada

        # 2. Factura emitida
        if invoice.move_type == 'out_invoice':
            partner = invoice.partner_id

            # F2: simplificada sin identificación (cliente sin NIF)
            if not partner.vat or partner.vat.strip() == "" or partner.vat.upper() == "SINNIF":
                return "F2"

            # F1: factura completa si tiene NIF válido
            return "F1"

        # 3. Factura recibida (no suele aplicarse en Verifactu, pero por si acaso)
        if invoice.move_type == 'in_invoice':
            return "F5"  # Sustitución rectificativa (dependerá del contexto)

        # 4. Valor por defecto si no se puede determinar
        return "F1"
