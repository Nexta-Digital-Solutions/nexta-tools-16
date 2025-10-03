# Desarrollado por Juan Ormaechea (Mr. Rubik) — Odoo Proprietary License v1.0

import logging
import base64

from odoo import models, fields, api, release, _
from odoo.exceptions import ValidationError, UserError
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


def _get_company(env):
    """Compat: Odoo 10 no tiene env.company; usar user.company_id (sirve 10–18)."""
    return env.user.company_id

def _is_modern(env):
    """Odoo 13+ → display_notification disponible."""
    try:
        major = int(str(getattr(release, 'major_version', '') or release.version).split('.')[0])
    except Exception:
        major = 13 if hasattr(env, 'company') else 12
    return major >= 13

def _notify_success(env, title, message, sticky=False):
    if _is_modern(env):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': 'success', 'sticky': bool(sticky)},
        }
    # ≤ Odoo 12 → rainbow man
    return {'effect': {'fadeout': 'slow', 'message': u"%s\n%s" % (title or '', message or ''), 'type': 'rainbow_man'}}

def _notify_error(env, title, message, sticky=True):
    if _is_modern(env):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': 'danger', 'sticky': bool(sticky)},
        }
    # ≤ Odoo 12 → error duro para que se vea en UI
    raise UserError(u"%s\n%s" % (title or _("Error"), message or ""))


class VerifactuEndpointConfig(models.Model):
    _name = 'verifactu.endpoint.config'
    _description = 'Configuración persistente del Endpoint VeriFactu'
    _rec_name = 'endpoint_url'

    # Ajustes generales
    anomaly_cron_enabled = fields.Boolean(string="Activar detección de anomalías automática")
    endpoint_url = fields.Char("URL del endpoint de VeriFactu", default="")
    # Producción AEAT (referencia): https://prewww1.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP

    # Certificado
    cert_pfx = fields.Binary("Certificado PFX", attachment=True)
    cert_pfx_filename = fields.Char("Nombre del archivo PFX")
    # OJO: no usar password=True aquí; va en la VISTA XML.
    cert_password = fields.Char(string="Contraseña del certificado")

    company_id = fields.Many2one(
        'res.company',
        string="Compañía",
        default=lambda self: _get_company(self.env),
        required=True,
        index=True,
    )

    show_qr_always = fields.Boolean(
        string="Mostrar siempre el QR en la factura",
        default=True,
        help="Si está activado, el código QR se incluirá en todas las facturas, incluso si no se envían a la AEAT."
    )

    cron_auto_send_enabled = fields.Boolean(
        string="Activar envío automático periódico",
        default=False,
        help="Si está activado, se enviarán automáticamente las facturas pendientes a VeriFactu mediante el cron."
    )

    auto_send_to_verifactu = fields.Boolean(
        string="Enviar automáticamente a VeriFactu al confirmar",
        default=False,
        help="Si está activo, las facturas se enviarán automáticamente a VeriFactu al validar (estado 'posted')."
    )

    # Información del Sistema Informático
    verifactu_system_name = fields.Char(string="Nombre del sistema informático")
    verifactu_system_id = fields.Char(string="ID del sistema")
    verifactu_system_version = fields.Char(string="Versión")
    verifactu_system_installation_number = fields.Char(string="Número de instalación")
    verifactu_system_use_only_verifactu = fields.Selection(
        selection=[('S', 'Sí'), ('N', 'No')], string="Solo se usa para VeriFactu"
    )
    verifactu_system_multi_ot = fields.Selection(
        selection=[('S', 'Sí'), ('N', 'No')], string="Múltiples OT"
    )
    verifactu_system_multiple_ot_indicator = fields.Selection(
        selection=[('S', 'Sí'), ('N', 'No')], string="Indicador de múltiples OT"
    )

    # -----------------------
    # Carga por defecto (singleton por compañía)
    # -----------------------
    @api.model
    def default_get(self, fields_list):
        if self.env.context.get('no_default'):
            return super(VerifactuEndpointConfig, self).default_get(fields_list)

        config = self.get_singleton_record()
        res = super(VerifactuEndpointConfig, self).default_get(fields_list)

        vals = {
            'endpoint_url': config.endpoint_url,
            'cert_pfx': config.cert_pfx,
            'cert_pfx_filename': config.cert_pfx_filename,
            'cert_password': config.cert_password,
            'show_qr_always': config.show_qr_always,
            'auto_send_to_verifactu': config.auto_send_to_verifactu,
            'cron_auto_send_enabled': config.cron_auto_send_enabled,
            'verifactu_system_name': config.verifactu_system_name,
            'verifactu_system_id': config.verifactu_system_id,
            'verifactu_system_version': config.verifactu_system_version,
            'verifactu_system_installation_number': config.verifactu_system_installation_number,
            'verifactu_system_use_only_verifactu': config.verifactu_system_use_only_verifactu,
            'verifactu_system_multi_ot': config.verifactu_system_multi_ot,
            'verifactu_system_multiple_ot_indicator': config.verifactu_system_multiple_ot_indicator,
        }
        for k in list(vals.keys()):
            if k not in fields_list:
                vals.pop(k)
        res.update(vals)

        logger.info("📂 Datos del singleton cargados en el formulario")
        return res

    @api.model
    def get_singleton_record(self):
        company = _get_company(self.env)
        config = self.sudo().search([('company_id', '=', company.id)], limit=1)
        if not config:
            config = self.sudo().with_context(no_default=True).create({
                'company_id': company.id,
                'endpoint_url': '',
                'cert_pfx_filename': '',
                'cert_password': '',
                'show_qr_always': True,
                'auto_send_to_verifactu': False,
                'cron_auto_send_enabled': False,
            })
            logger.info("🆕 Registro singleton creado para VeriFactu (%s)", company.name)
        return config

    # -----------------------
    # Onchange
    # -----------------------
    @api.onchange('cert_pfx')
    def _onchange_cert_pfx(self):
        if self.cert_pfx and not self.cert_pfx_filename:
            filename = self._context.get('filename') or 'certificado.pfx'
            self.cert_pfx_filename = filename
            logger.info("📁 Archivo PFX cargado: %s", filename)

    # -----------------------
    # Acciones (botones)
    # -----------------------
    def _validate_endpoint(self):
        if self.endpoint_url:
            url = (self.endpoint_url or '').strip()
            if not url.lower().startswith('https://'):
                logger.error("URL inválida: %s", url)
                # Validación de datos → ValidationError estándar
                raise ValidationError(_("La URL debe comenzar por 'https://' y ser válida."))
            self.endpoint_url = url

    def save_config(self):
        self.ensure_one()
        self._validate_endpoint()

        if self.cert_pfx and not self.cert_pfx_filename:
            self.cert_pfx_filename = 'certificado.pfx'
            logger.info("🔐 Certificado PFX asignado: %s", self.cert_pfx_filename)

        singleton = self.get_singleton_record()
        singleton.write({
            'endpoint_url': self.endpoint_url,
            'cert_pfx': self.cert_pfx,
            'cert_pfx_filename': self.cert_pfx_filename,
            'cert_password': self.cert_password,
            'show_qr_always': self.show_qr_always,
            'auto_send_to_verifactu': self.auto_send_to_verifactu,
            'cron_auto_send_enabled': self.cron_auto_send_enabled,
            'verifactu_system_name': self.verifactu_system_name,
            'verifactu_system_id': self.verifactu_system_id,
            'verifactu_system_version': self.verifactu_system_version,
            'verifactu_system_installation_number': self.verifactu_system_installation_number,
            'verifactu_system_use_only_verifactu': self.verifactu_system_use_only_verifactu,
            'verifactu_system_multi_ot': self.verifactu_system_multi_ot,
            'verifactu_system_multiple_ot_indicator': self.verifactu_system_multiple_ot_indicator,
        })

        return _notify_success(self.env, '✅ Configuración guardada', _('Los datos han sido guardados correctamente.'))

    def action_reset_certificate(self):
        self.ensure_one()
        self.write({
            'cert_pfx': False,
            'cert_pfx_filename': '',
            'cert_password': '',
        })
        logger.info("🗑️ Certificado reseteado para el endpoint: %s", self.endpoint_url)
        return _notify_success(self.env, '🗑️ Certificado eliminado', _('El certificado ha sido eliminado correctamente.'))

    def action_test_certificate(self):
        self.ensure_one()

        if not self.cert_pfx or not self.cert_password:
            logger.error("🚫 Prueba de certificado fallida: falta el certificado o la contraseña.")
            # Error operativo → helper (UserError en ≤12)
            return _notify_error(self.env, 'Certificado', _('Falta el certificado o la contraseña.'))

        try:
            cert_data = base64.b64decode(self.cert_pfx)
            pkcs12.load_key_and_certificates(
                cert_data,
                self.cert_password.encode('utf-8'),
                backend=default_backend()
            )
            logger.info("🔓 Certificado válido para el endpoint: %s", self.endpoint_url)
            return _notify_success(self.env, '✅ Certificado válido', _('El certificado ha sido cargado correctamente.'))

        except ValueError as e:
            logger.error("🛑 Error de contraseña o archivo corrupto: %s", e)
            return _notify_error(self.env, 'Certificado', _('Contraseña incorrecta o archivo PFX corrupto.'))

        except Exception as e:
            logger.exception("❗ Error inesperado al cargar el certificado: %s", e)
            return _notify_error(self.env, 'Certificado', _('Error inesperado al cargar el certificado: %s') % e)
