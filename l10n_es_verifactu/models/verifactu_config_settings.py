# models/res_config_settings.py
# Desarrollado por Juan Ormaechea (Mr. Rubik) — Odoo Proprietary License v1.0

import requests
from odoo import _, models, fields, api, release
from odoo.exceptions import UserError

REQUEST_TIMEOUT = 8
PARAM_KEY = 'verifactu.declaracion_attachment_id'

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
    # <= Odoo 12 → rainbow man
    return {'effect': {'fadeout': 'slow', 'message': u"%s\n%s" % (title or '', message or ''), 'type': 'rainbow_man'}}

def _notify_error(env, title, message, sticky=True):
    if _is_modern(env):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': title, 'message': message, 'type': 'danger', 'sticky': bool(sticky)},
        }
    # <= Odoo 12 → errores con UserError
    raise UserError(u"%s\n%s" % (title or _("Error"), message or ""))

def _get_company(env):
    return env.user.company_id

class VerifactuResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # --- Config VeriFactu existente ---
    endpoint_url = fields.Char("URL del endpoint VeriFactu")
    show_qr_always = fields.Boolean("Mostrar siempre el QR")
    auto_send_to_verifactu = fields.Boolean("Envío automático al validar")
    cron_auto_send_enabled = fields.Boolean("Activar envío periódico")

    # El enmascarado va en la VISTA
    cert_password = fields.Char("Contraseña del certificado")
    cert_pfx = fields.Binary("Certificado PFX", attachment=True)
    cert_pfx_filename = fields.Char("Nombre del archivo PFX", readonly=True)

    verifactu_system_name = fields.Char("Nombre del Sistema Informático")
    verifactu_system_id = fields.Char("ID del Sistema Informático")
    verifactu_system_version = fields.Char("Versión del Sistema")
    verifactu_system_installation_number = fields.Char("Número de Instalación")
    verifactu_system_use_only_verifactu = fields.Selection([('S','Sí'),('N','No')], string="Solo uso VeriFactu")
    verifactu_system_multi_ot = fields.Selection([('S','Sí'),('N','No')], string="Multi OT posible")
    verifactu_system_multiple_ot_indicator = fields.Selection([('S','Sí'),('N','No')], string="Indicador múltiples OT")

    # --- Licencia ---
    verifactu_license_key = fields.Char(string="Clave de licencia")
    verifactu_license_token = fields.Text(string="Token de licencia (JWT)", readonly=True)
    verifactu_license_status = fields.Selection(
        [("valid","Válida"),("grace","Gracia"),("invalid","Inválida"),("expired","Expirada")],
        string="Estado de licencia", readonly=True
    )
    verifactu_license_server_url = fields.Char(
        string="URL del servidor de licencias",
        help="Servicio HTTPS que emite y firma los tokens de licencia (JWT).",
        default="https://us-central1-verifactu-7fc70.cloudfunctions.net/issueLicense"
    )
    verifactu_update_feed_url = fields.Char(
        string="URL del feed de actualizaciones",
        default="https://firebasestorage.googleapis.com/v0/b/verifactu-7fc70.firebasestorage.app/o/latest.json?alt=media&token=1ad6b4a7-4b7e-4bde-bba9-ac7c2ca995e1",
    )
    verifactu_updates_cron_enabled = fields.Boolean(
        string="Activar comprobación periódica de actualizaciones",
        help="Si está activado, se revisará el feed y se notificará cuando haya nueva versión."
    )
    verifactu_license_token_display = fields.Char(string="Token (JWT)", readonly=True)

    verifactu_declaracion_file = fields.Binary(string="Declaración Responsable", attachment=True)
    verifactu_declaracion_filename = fields.Char(string="Nombre del archivo")
    verifactu_declaracion_has_attachment = fields.Boolean(
        string="Hay adjunto", compute="_compute_declaracion_has_attachment"
    )

    def _compute_declaracion_has_attachment(self):
        icp = self.env['ir.config_parameter'].sudo()
        att_id = icp.get_param(PARAM_KEY)
        for rec in self:
            rec.verifactu_declaracion_has_attachment = bool(att_id)

    # ---------- Acciones UI (declaración responsable) ----------
    def action_download_declaracion(self):
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        att_id = ICP.get_param(PARAM_KEY)

        if not att_id:
            if not self.verifactu_declaracion_file:
                # error → usa helper de error (UserError en <=12)
                return _notify_error(self.env, "Declaración", _("No hay documento cargado aún."))
            att = self.env['ir.attachment'].sudo().create({
                'name': self.verifactu_declaracion_filename or 'Declaracion_Responsable.pdf',
                'datas': self.verifactu_declaracion_file,
                'mimetype': 'application/pdf',
                'public': True,
            })
            ICP.set_param(PARAM_KEY, str(att.id))
            att_id = att.id

        filename = self.verifactu_declaracion_filename or 'Declaracion_Responsable.pdf'
        return {
            'type': 'ir.actions.act_url',
            'target': 'self',
            'url': '/web/content/%s?download=1&filename=%s' % (int(att_id), filename),
        }

    # ---------- LOAD (ajustes) ----------
    @api.model
    def get_values(self):
        res = super(VerifactuResConfigSettings, self).get_values()

        config = self.env['verifactu.endpoint.config'].sudo().get_singleton_record()
        res.update({
            'endpoint_url': config.endpoint_url,
            'show_qr_always': config.show_qr_always,
            'auto_send_to_verifactu': config.auto_send_to_verifactu,
            'cron_auto_send_enabled': config.cron_auto_send_enabled,
            'cert_password': config.cert_password,
            'cert_pfx': config.cert_pfx,
            'cert_pfx_filename': config.cert_pfx_filename,
            'verifactu_system_name': config.verifactu_system_name,
            'verifactu_system_id': config.verifactu_system_id,
            'verifactu_system_version': config.verifactu_system_version,
            'verifactu_system_installation_number': config.verifactu_system_installation_number,
            'verifactu_system_use_only_verifactu': config.verifactu_system_use_only_verifactu,
            'verifactu_system_multi_ot': config.verifactu_system_multi_ot,
            'verifactu_system_multiple_ot_indicator': config.verifactu_system_multiple_ot_indicator,
        })

        lic = self.env["verifactu.license"].sudo().get_singleton_record()
        res.update({
            "verifactu_license_key": lic.license_key,
            "verifactu_license_token": lic.license_token,
            "verifactu_license_status": lic.license_status,
            "verifactu_update_feed_url": lic.update_feed_url,
            "verifactu_license_server_url": lic.verifactu_license_server_url,
            "verifactu_updates_cron_enabled": lic.updates_cron_enabled,
            "verifactu_license_token_display": lic.license_token_display,
        })

        ICP = self.env['ir.config_parameter'].sudo()
        att_id = ICP.get_param(PARAM_KEY)
        if att_id:
            att = self.env['ir.attachment'].sudo().browse(int(att_id))
            if att.exists():
                res.update({'verifactu_declaracion_file': att.datas, 'verifactu_declaracion_filename': att.name})
        return res

    # ---------- SAVE (ajustes) ----------
    def set_values(self):
        super(VerifactuResConfigSettings, self).set_values()

        config = self.env['verifactu.endpoint.config'].sudo().get_singleton_record()
        config.write({
            'endpoint_url': self.endpoint_url,
            'show_qr_always': self.show_qr_always,
            'auto_send_to_verifactu': self.auto_send_to_verifactu,
            'cron_auto_send_enabled': self.cron_auto_send_enabled,
            'cert_password': self.cert_password,
            'cert_pfx': self.cert_pfx,
            'cert_pfx_filename': self.cert_pfx_filename,
            'verifactu_system_name': self.verifactu_system_name,
            'verifactu_system_id': self.verifactu_system_id,
            'verifactu_system_version': self.verifactu_system_version,
            'verifactu_system_installation_number': self.verifactu_system_installation_number,
            'verifactu_system_use_only_verifactu': self.verifactu_system_use_only_verifactu,
            'verifactu_system_multi_ot': self.verifactu_system_multi_ot,
            'verifactu_system_multiple_ot_indicator': self.verifactu_system_multiple_ot_indicator,
        })

        lic = self.env["verifactu.license"].sudo().get_singleton_record()
        lic.write({
            "license_key": self.verifactu_license_key,
            "update_feed_url": self.verifactu_update_feed_url,
            "verifactu_license_server_url": self.verifactu_license_server_url,
            "updates_cron_enabled": self.verifactu_updates_cron_enabled,
        })

        cron = self.env.ref("l10n_es_verifactu.ir_cron_verifactu_update_checker", raise_if_not_found=False)
        if cron:
            cron.sudo().write({"active": bool(self.verifactu_updates_cron_enabled)})

        ICP = self.env['ir.config_parameter'].sudo()
        att_id = ICP.get_param(PARAM_KEY) or False
        if self.verifactu_declaracion_file:
            name = self.verifactu_declaracion_filename or "Declaracion_Responsable.pdf"
            vals = {'name': name, 'datas': self.verifactu_declaracion_file, 'mimetype': 'application/pdf', 'public': True}
            if att_id:
                att = self.env['ir.attachment'].sudo().browse(int(att_id))
                if att.exists():
                    att.write(vals)
                    return
            att = self.env['ir.attachment'].sudo().create(vals)
            ICP.set_param(PARAM_KEY, str(att.id))

    # ---------- Acciones puente ----------
    def action_test_certificate(self):
        # Esta acción ya devuelve notificaciones desde verifactu.endpoint.config
        return self.env['verifactu.endpoint.config'].sudo().get_singleton_record().action_test_certificate()

    def action_reset_certificate(self):
        return self.env['verifactu.endpoint.config'].sudo().get_singleton_record().action_reset_certificate()

    def save_config(self):
        return self.env['verifactu.endpoint.config'].sudo().get_singleton_record().save_config()

    # ---------- Licencia: emisión/verify ----------
    def action_issue_license_token(self):
        self.ensure_one()
        Lic = self.env["verifactu.license"].sudo()
        lic = Lic.get_singleton_record()

        url = (lic.verifactu_license_server_url or "").strip()
        if not url:
            return _notify_error(self.env, "Licencia", _("No hay URL de servidor configurada."))

        icp = self.env["ir.config_parameter"].sudo()
        db_uuid = icp.get_param("database.uuid") or ""
        base_url = (icp.get_param("web.base.url") or "").strip()
        module_version = icp.get_param("verifactu.module_version") or "1.0.8"

        company = _get_company(self.env)
        company_name = (company.display_name or company.name or "no-name").strip()[:200]

        license_key = (lic.license_key or "").strip()
        if not license_key:
            return _notify_error(self.env, "Licencia", _("Introduce la clave de licencia."))

        payload = {
            "license_key": license_key,
            "db_uuid": db_uuid,
            "base_url": base_url,
            "company_name": company_name,
            "module": "l10n_es_verifactu",
            "module_version": module_version,
        }

        try:
            resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError:
                return _notify_error(self.env, "Licencia", _("El servidor respondió, pero no devolvió JSON válido."))

            token = data.get("token")
            if not token:
                err_msg = data.get("error") or _("El servidor no devolvió un token válido.")
                return _notify_error(self.env, "Licencia", err_msg)

            lic.write({
                "license_token": token,
                "license_status": "valid",
                "last_check": fields.Datetime.now(),
                "last_error": False,
            })
            self.env["verifactu.license.guard"].sudo().verify_license()
            return _notify_success(self.env, "Licencia", _("Token recibido y verificado."))

        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else None
            server_msg = None
            try:
                server_msg = e.response.json().get("error")
            except Exception:
                pass

            if status == 400:
                msg = server_msg or _("Solicitud inválida. Revisa la clave de licencia y los datos enviados.")
            elif status == 401:
                msg = server_msg or _("Licencia no autorizada. Verifica que tu clave sea correcta y esté activa.")
            elif status == 403:
                msg = server_msg or _("Acceso prohibido. Esta base de datos o URL no está autorizada para esa licencia.")
            elif status == 404:
                msg = server_msg or _("No se encontró el servicio de licencias. Verifica la URL configurada.")
            elif status and status >= 500:
                msg = server_msg or _("El servidor de licencias ha devuelto un error interno. Inténtalo más tarde.")
            else:
                msg = server_msg or _("Error inesperado al contactar con el servidor (código %s).") % status

            lic.write({"license_status": "invalid", "last_error": msg, "last_check": fields.Datetime.now()})
            return _notify_error(self.env, "Licencia", msg)

        except requests.exceptions.Timeout:
            msg = _("Tiempo de espera agotado al contactar con el servidor de licencias. Inténtalo de nuevo.")
            lic.write({"license_status": "invalid", "last_error": msg, "last_check": fields.Datetime.now()})
            return _notify_error(self.env, "Licencia", msg)

        except requests.exceptions.ConnectionError:
            msg = _("No se pudo establecer conexión con el servidor de licencias. Revisa la red o la URL configurada.")
            lic.write({"license_status": "invalid", "last_error": msg, "last_check": fields.Datetime.now()})
            return _notify_error(self.env, "Licencia", msg)

        except Exception as e:
            msg = _("Error procesando la respuesta: %s") % e
            lic.write({"license_status": "invalid", "last_error": str(e), "last_check": fields.Datetime.now()})
            return _notify_error(self.env, "Licencia", msg)

    def action_verify_license_now(self):
        self.ensure_one()
        self.env["verifactu.license.guard"].sudo().verify_license()
        return _notify_success(self.env, "Licencia", _("Verificación ejecutada."))
