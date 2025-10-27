# -*- coding: utf-8 -*-
# models/res_config_settings.py
# Desarrollado por Juan Ormaechea (Mr. Rubik) — Odoo Proprietary License v1.0

import requests
import pytz
from datetime import timedelta
from odoo import _, models, fields, api, release
from odoo.exceptions import UserError

REQUEST_TIMEOUT = 8
PARAM_KEY = 'verifactu.declaracion_attachment_id'


# ───────────────────────── Helpers de compatibilidad ─────────────────────────

def _odoo_major():
    try:
        return int(str(getattr(release, 'major_version', '') or release.version).split('.')[0])
    except Exception:
        # Heurística conservadora
        return 13

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


MAJOR = _odoo_major()

# ──────────────────────────── Definiciones por versión ───────────────────────

if MAJOR >= 11:
    # ───────────────────── Mixin ABSTRACTO (v11→18) ─────────────────────
    class VerifactuSettingsMixin(models.AbstractModel):
        _name = 'verifactu.settings.mixin'
        _description = 'Mixin de ajustes VeriFactu (11→18)'
        _auto = False  # Abstracto; no crea tabla

        # --- CRON / reintentos / ritmo (periódico) ---
        cron_batch_size = fields.Integer(string="Tamaño de lote (batch)", default=5,
                                         help="Máximo de facturas por pasada del cron.")
        retry_backoff_min = fields.Integer(string="Backoff base (min)", default=10,
                                           help="Minutos para el primer reintento; luego crece exponencialmente.")
        retry_backoff_cap_min = fields.Integer(string="Backoff tope (min)", default=60,
                                               help="Tope máximo de espera entre reintentos por factura.")
        request_min_interval_sec = fields.Integer(string="Intervalo mínimo entre envíos (s)", default=60,
                                                  help="Margen mínimo entre peticiones al portal por compañía (rate-limit).")

        # --- CRON DIARIO (a una hora fija) ---
        daily_auto_send_enabled = fields.Boolean(string="Activar envío diario a una hora", default=False,
                                                 help="Si está activado, se ejecutará un CRON diario a la hora indicada.")
        daily_send_time = fields.Char(string="Hora diaria (HH:MM)", default="03:00",
                                      help="Hora local de la compañía (formato HH:MM).")

        # --- Parámetros PROPIOS del CRON diario ---
        daily_use_custom_params = fields.Boolean(string="Usar parámetros propios en el envío diario", default=False,
                                                 help="Si está activo, el cron diario usará estos parámetros en lugar de los del cron periódico.")
        daily_cron_batch_size = fields.Integer(string="Tamaño de lote (diario)", default=5,
                                               help="Máximo de facturas por pasada del cron diario.")
        daily_retry_backoff_min = fields.Integer(string="Backoff base (min) diario", default=10,
                                                 help="Minutos para el primer reintento en el cron diario; luego crece exponencialmente.")
        daily_retry_backoff_cap_min = fields.Integer(string="Backoff tope (min) diario", default=60,
                                                     help="Tope máximo de espera entre reintentos por factura en el cron diario.")
        daily_request_min_interval_sec = fields.Integer(string="Intervalo mínimo entre envíos (s) diario", default=60,
                                                        help="Margen mínimo entre peticiones al portal por compañía en el cron diario (rate-limit).")

        # --- Config VeriFactu existente ---
        endpoint_url = fields.Char("URL del endpoint VeriFactu")
        show_qr_always = fields.Boolean("Mostrar siempre el QR")
        auto_send_to_verifactu = fields.Boolean("Envío automático al validar")
        cron_auto_send_enabled = fields.Boolean("Activar envío periódico")

        # Certificado
        cert_password = fields.Char("Contraseña del certificado")
        cert_pfx = fields.Binary("Certificado PFX", attachment=True)
        cert_pfx_filename = fields.Char("Nombre del archivo PFX", readonly=True)

        # Sistema Informático
        verifactu_system_name = fields.Char("Nombre del Sistema Informático")
        verifactu_system_id = fields.Char("ID del Sistema Informático")
        verifactu_system_version = fields.Char("Versión del Sistema")
        verifactu_system_installation_number = fields.Char("Número de Instalación")
        verifactu_system_use_only_verifactu = fields.Selection([('S', 'Sí'), ('N', 'No')], string="Solo uso VeriFactu")
        verifactu_system_multi_ot = fields.Selection([('S', 'Sí'), ('N', 'No')], string="Multi OT posible")
        verifactu_system_multiple_ot_indicator = fields.Selection([('S', 'Sí'), ('N', 'No')], string="Indicador múltiples OT")

        # --- Licencia ---
        verifactu_license_key = fields.Char(string="Clave de licencia")
        verifactu_license_token = fields.Text(string="Token de licencia (JWT)", readonly=True)
        verifactu_license_status = fields.Selection(
            [("valid", "Válida"), ("grace", "Gracia"), ("invalid", "Inválida"), ("expired", "Expirada")],
            string="Estado de licencia", readonly=True)
        verifactu_license_server_url = fields.Char(
            string="URL del servidor de licencias",
            help="Servicio HTTPS que emite y firma los tokens de licencia (JWT).",
            default="https://us-central1-verifactu-7fc70.cloudfunctions.net/issueLicense")
        verifactu_update_feed_url = fields.Char(
            string="URL del feed de actualizaciones",
            default="https://firebasestorage.googleapis.com/v0/b/verifactu-7fc70.firebasestorage.app/o/latest.json?alt=media&token=1ad6b4a7-4b7e-4bde-bba9-ac7c2ca995e1")
        verifactu_updates_cron_enabled = fields.Boolean(
            string="Activar comprobación periódica de actualizaciones",
            help="Si está activado, se revisará el feed y se notificará cuando haya nueva versión.")
        verifactu_license_token_display = fields.Char(string="Token (JWT)", readonly=True)

        # Declaración responsable
        verifactu_declaracion_file = fields.Binary(string="Declaración Responsable", attachment=True)
        verifactu_declaracion_filename = fields.Char(string="Nombre del archivo")
        verifactu_declaracion_has_attachment = fields.Boolean(
            string="Hay adjunto", compute="_compute_declaracion_has_attachment")

        # ───────────── Helpers TZ/nextcall (para CRON diario) ─────────────
        @api.model
        def _company_tz(self):
            tz = (self.env.user.company_id.tz or
                  getattr(getattr(self.env, 'company', None), 'tz', None) or
                  'UTC')
            try:
                return pytz.timezone(tz)
            except Exception:
                return pytz.UTC

        @api.model
        def _compute_daily_nextcall_utc(self, hhmm):
            try:
                hh, mm = (hhmm or '03:00').split(':')
                hh = int(hh); mm = int(mm)
            except Exception:
                hh, mm = 3, 0

            tz = self._company_tz()
            now_utc = fields.Datetime.now()
            now_local = pytz.UTC.localize(now_utc).astimezone(tz)
            run_local = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if run_local <= now_local:
                run_local = run_local + timedelta(days=1)
            run_utc = run_local.astimezone(pytz.UTC).replace(tzinfo=None)
            return fields.Datetime.to_string(run_utc)

        # ---------- Acciones UI (declaración responsable) ----------
        def _compute_declaracion_has_attachment(self):
            icp = self.env['ir.config_parameter'].sudo()
            att_id = icp.get_param(PARAM_KEY)
            for rec in self:
                rec.verifactu_declaracion_has_attachment = bool(att_id)

        def action_download_declaracion(self):
            self.ensure_one()
            ICP = self.env['ir.config_parameter'].sudo()
            att_id = ICP.get_param(PARAM_KEY)

            if not att_id:
                if not self.verifactu_declaracion_file:
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
        def _vf_get_values_dict(self):
            config = self.env['verifactu.endpoint.config'].sudo().get_singleton_record()
            res = {
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
                # Periódico
                'cron_batch_size': getattr(config, 'cron_batch_size', 5),
                'retry_backoff_min': getattr(config, 'retry_backoff_min', 10),
                'retry_backoff_cap_min': getattr(config, 'retry_backoff_cap_min', 60),
                'request_min_interval_sec': getattr(config, 'request_min_interval_sec', 60),
                # Diario
                'daily_auto_send_enabled': getattr(config, 'daily_auto_send_enabled', False),
                'daily_send_time': getattr(config, 'daily_send_time', '03:00'),
                'daily_use_custom_params': getattr(config, 'daily_use_custom_params', False),
                'daily_cron_batch_size': getattr(config, 'daily_cron_batch_size', 5),
                'daily_retry_backoff_min': getattr(config, 'daily_retry_backoff_min', 10),
                'daily_retry_backoff_cap_min': getattr(config, 'daily_retry_backoff_cap_min', 60),
                'daily_request_min_interval_sec': getattr(config, 'daily_request_min_interval_sec', 60),
            }

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
                    res.update({'verifactu_declaracion_file': att.datas,
                                'verifactu_declaracion_filename': att.name})
            return res

        # ---------- SAVE (ajustes) ----------
        def _vf_write_config_from_self(self):
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
                # Periódico
                'cron_batch_size': self.cron_batch_size or 5,
                'retry_backoff_min': self.retry_backoff_min or 10,
                'retry_backoff_cap_min': self.retry_backoff_cap_min or 60,
                'request_min_interval_sec': self.request_min_interval_sec or 60,
                # Diario
                'daily_auto_send_enabled': bool(self.daily_auto_send_enabled),
                'daily_send_time': self.daily_send_time or '03:00',
                'daily_use_custom_params': bool(self.daily_use_custom_params),
                'daily_cron_batch_size': self.daily_cron_batch_size or 5,
                'daily_retry_backoff_min': self.daily_retry_backoff_min or 10,
                'daily_retry_backoff_cap_min': self.daily_retry_backoff_cap_min or 60,
                'daily_request_min_interval_sec': self.daily_request_min_interval_sec or 60,
            })

            # Activación CRON periódico global
            try:
                cron_send = self.env.ref("l10n_es_verifactu.ir_cron_send_pending_verifactu", raise_if_not_found=False)
                if cron_send:
                    any_enabled = bool(self.env['verifactu.endpoint.config'].sudo().search_count(
                        [('cron_auto_send_enabled', '=', True)]))
                    cron_send.sudo().write({'active': any_enabled})
            except Exception:
                pass

            # CRON diario a una hora concreta
            try:
                cron_daily = self.env.ref('l10n_es_verifactu.ir_cron_verifactu_send_daily', raise_if_not_found=False)
                if cron_daily:
                    if self.daily_auto_send_enabled:
                        nextcall = self._compute_daily_nextcall_utc(self.daily_send_time or '03:00')
                        cron_daily.sudo().write({
                            'active': True,
                            'interval_number': 1,
                            'interval_type': 'days',
                            'nextcall': nextcall,
                        })
                    else:
                        cron_daily.sudo().write({'active': False})
            except Exception:
                pass

            # Licencia
            lic = self.env["verifactu.license"].sudo().get_singleton_record()
            lic.write({
                "license_key": self.verifactu_license_key,
                "update_feed_url": self.verifactu_update_feed_url,
                "verifactu_license_server_url": self.verifactu_license_server_url,
                "updates_cron_enabled": self.verifactu_updates_cron_enabled,
            })

            # Toggle cron updates (si existe)
            cron_updates = self.env.ref("l10n_es_verifactu.ir_cron_verifactu_update_checker", raise_if_not_found=False)
            if cron_updates:
                cron_updates.sudo().write({"active": bool(self.verifactu_updates_cron_enabled)})

            # Declaración responsable (guardar adjunto)
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

    # ───── Clase concreta v11→18 ─────
    class VerifactuResConfigSettings(models.TransientModel):
        _name = 'res.config.settings'                         # 👈 forzamos el mismo nombre del modelo base
        _inherit = ['res.config.settings', 'verifactu.settings.mixin']
        _description = 'Ajustes VeriFactu (res.config.settings)'

        @api.model
        def get_values(self):
            try:
                res = super(VerifactuResConfigSettings, self).get_values()
            except AttributeError:
                res = {}
            res.update(self._vf_get_values_dict())
            return res

        def set_values(self):
            try:
                super(VerifactuResConfigSettings, self).set_values()
            except AttributeError:
                pass
            self._vf_write_config_from_self()

else:
    # ───────────────────── Clase v10 (sin herencia múltiple) ──────────────────
    class VerifactuBaseConfigSettings(models.TransientModel):
        _inherit = 'base.config.settings'  # SOLO uno en v10

        # ===== Campos (duplicados desde el mixin) =====
        cron_batch_size = fields.Integer(string="Tamaño de lote (batch)", default=5)
        retry_backoff_min = fields.Integer(string="Backoff base (min)", default=10)
        retry_backoff_cap_min = fields.Integer(string="Backoff tope (min)", default=60)
        request_min_interval_sec = fields.Integer(string="Intervalo mínimo entre envíos (s)", default=60)

        daily_auto_send_enabled = fields.Boolean(string="Activar envío diario a una hora", default=False)
        daily_send_time = fields.Char(string="Hora diaria (HH:MM)", default="03:00")

        daily_use_custom_params = fields.Boolean(string="Usar parámetros propios en el envío diario", default=False)
        daily_cron_batch_size = fields.Integer(string="Tamaño de lote (diario)", default=5)
        daily_retry_backoff_min = fields.Integer(string="Backoff base (min) diario", default=10)
        daily_retry_backoff_cap_min = fields.Integer(string="Backoff tope (min) diario", default=60)
        daily_request_min_interval_sec = fields.Integer(string="Intervalo mínimo entre envíos (s) diario", default=60)

        endpoint_url = fields.Char("URL del endpoint VeriFactu")
        show_qr_always = fields.Boolean("Mostrar siempre el QR")
        auto_send_to_verifactu = fields.Boolean("Envío automático al validar")
        cron_auto_send_enabled = fields.Boolean("Activar envío periódico")

        cert_password = fields.Char("Contraseña del certificado")
        cert_pfx = fields.Binary("Certificado PFX", attachment=True)
        cert_pfx_filename = fields.Char("Nombre del archivo PFX", readonly=True)

        verifactu_system_name = fields.Char("Nombre del Sistema Informático")
        verifactu_system_id = fields.Char("ID del Sistema Informático")
        verifactu_system_version = fields.Char("Versión del Sistema")
        verifactu_system_installation_number = fields.Char("Número de Instalación")
        verifactu_system_use_only_verifactu = fields.Selection([('S', 'Sí'), ('N', 'No')], string="Solo uso VeriFactu")
        verifactu_system_multi_ot = fields.Selection([('S', 'Sí'), ('N', 'No')], string="Multi OT posible")
        verifactu_system_multiple_ot_indicator = fields.Selection([('S', 'Sí'), ('N', 'No')], string="Indicador múltiples OT")

        verifactu_license_key = fields.Char(string="Clave de licencia")
        verifactu_license_token = fields.Text(string="Token de licencia (JWT)", readonly=True)
        verifactu_license_status = fields.Selection(
            [("valid", "Válida"), ("grace", "Gracia"), ("invalid", "Inválida"), ("expired", "Expirada")],
            string="Estado de licencia", readonly=True)
        verifactu_license_server_url = fields.Char(
            string="URL del servidor de licencias",
            default="https://us-central1-verifactu-7fc70.cloudfunctions.net/issueLicense")
        verifactu_update_feed_url = fields.Char(
            string="URL del feed de actualizaciones",
            default="https://firebasestorage.googleapis.com/v0/b/verifactu-7fc70.firebasestorage.app/o/latest.json?alt=media&token=1ad6b4a7-4b7e-4bde-bba9-ac7c2ca995e1")
        verifactu_updates_cron_enabled = fields.Boolean(string="Activar comprobación periódica de actualizaciones")
        verifactu_license_token_display = fields.Char(string="Token (JWT)", readonly=True)

        verifactu_declaracion_file = fields.Binary(string="Declaración Responsable", attachment=True)
        verifactu_declaracion_filename = fields.Char(string="Nombre del archivo")
        verifactu_declaracion_has_attachment = fields.Boolean(
            string="Hay adjunto", compute="_compute_declaracion_has_attachment")

        # ===== Métodos (copiados del mixin) =====
        @api.model
        def _company_tz(self):
            tz = (self.env.user.company_id.tz or 'UTC')
            try:
                return pytz.timezone(tz)
            except Exception:
                return pytz.UTC

        @api.model
        def _compute_daily_nextcall_utc(self, hhmm):
            try:
                hh, mm = (hhmm or '03:00').split(':')
                hh = int(hh); mm = int(mm)
            except Exception:
                hh, mm = 3, 0
            tz = self._company_tz()
            now_utc = fields.Datetime.now()
            now_local = pytz.UTC.localize(now_utc).astimezone(tz)
            run_local = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if run_local <= now_local:
                run_local = run_local + timedelta(days=1)
            run_utc = run_local.astimezone(pytz.UTC).replace(tzinfo=None)
            return fields.Datetime.to_string(run_utc)

        def _compute_declaracion_has_attachment(self):
            icp = self.env['ir.config_parameter'].sudo()
            att_id = icp.get_param(PARAM_KEY)
            for rec in self:
                rec.verifactu_declaracion_has_attachment = bool(att_id)

        def action_download_declaracion(self):
            self.ensure_one()
            ICP = self.env['ir.config_parameter'].sudo()
            att_id = ICP.get_param(PARAM_KEY)
            if not att_id:
                if not self.verifactu_declaracion_file:
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

        @api.model
        def get_values(self):
            # En v10, el super puede no implementarlo
            try:
                res = super(VerifactuBaseConfigSettings, self).get_values()
            except AttributeError:
                res = {}
            # Recupera del singleton/licencia/adjunto
            config = self.env['verifactu.endpoint.config'].sudo().get_singleton_record()
            lic = self.env["verifactu.license"].sudo().get_singleton_record()
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
                'cron_batch_size': getattr(config, 'cron_batch_size', 5),
                'retry_backoff_min': getattr(config, 'retry_backoff_min', 10),
                'retry_backoff_cap_min': getattr(config, 'retry_backoff_cap_min', 60),
                'request_min_interval_sec': getattr(config, 'request_min_interval_sec', 60),
                'daily_auto_send_enabled': getattr(config, 'daily_auto_send_enabled', False),
                'daily_send_time': getattr(config, 'daily_send_time', '03:00'),
                'daily_use_custom_params': getattr(config, 'daily_use_custom_params', False),
                'daily_cron_batch_size': getattr(config, 'daily_cron_batch_size', 5),
                'daily_retry_backoff_min': getattr(config, 'daily_retry_backoff_min', 10),
                'daily_retry_backoff_cap_min': getattr(config, 'daily_retry_backoff_cap_min', 60),
                'daily_request_min_interval_sec': getattr(config, 'daily_request_min_interval_sec', 60),
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

        def set_values(self):
            # En v10, el super puede no implementarlo
            try:
                super(VerifactuBaseConfigSettings, self).set_values()
            except AttributeError:
                pass

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
                'cron_batch_size': self.cron_batch_size or 5,
                'retry_backoff_min': self.retry_backoff_min or 10,
                'retry_backoff_cap_min': self.retry_backoff_cap_min or 60,
                'request_min_interval_sec': self.request_min_interval_sec or 60,
                'daily_auto_send_enabled': bool(self.daily_auto_send_enabled),
                'daily_send_time': self.daily_send_time or '03:00',
                'daily_use_custom_params': bool(self.daily_use_custom_params),
                'daily_cron_batch_size': self.daily_cron_batch_size or 5,
                'daily_retry_backoff_min': self.daily_retry_backoff_min or 10,
                'daily_retry_backoff_cap_min': self.daily_retry_backoff_cap_min or 60,
                'daily_request_min_interval_sec': self.daily_request_min_interval_sec or 60,
            })

            try:
                cron_send = self.env.ref("l10n_es_verifactu.ir_cron_send_pending_verifactu", raise_if_not_found=False)
                if cron_send:
                    any_enabled = bool(self.env['verifactu.endpoint.config'].sudo().search_count(
                        [('cron_auto_send_enabled', '=', True)]))
                    cron_send.sudo().write({'active': any_enabled})
            except Exception:
                pass

            try:
                cron_daily = self.env.ref('l10n_es_verifactu.ir_cron_verifactu_send_daily', raise_if_not_found=False)
                if cron_daily:
                    if self.daily_auto_send_enabled:
                        nextcall = self._compute_daily_nextcall_utc(self.daily_send_time or '03:00')
                        cron_daily.sudo().write({
                            'active': True,
                            'interval_number': 1,
                            'interval_type': 'days',
                            'nextcall': nextcall,
                        })
                    else:
                        cron_daily.sudo().write({'active': False})
            except Exception:
                pass

            lic = self.env["verifactu.license"].sudo().get_singleton_record()
            lic.write({
                "license_key": self.verifactu_license_key,
                "update_feed_url": self.verifactu_update_feed_url,
                "verifactu_license_server_url": self.verifactu_license_server_url,
                "updates_cron_enabled": self.verifactu_updates_cron_enabled,
            })

            cron_updates = self.env.ref("l10n_es_verifactu.ir_cron_verifactu_update_checker", raise_if_not_found=False)
            if cron_updates:
                cron_updates.sudo().write({"active": bool(self.verifactu_updates_cron_enabled)})

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

        # ====== Hooks específicos v10 para cargar/guardar ======
        @api.model
        def default_get(self, fields_list):
            """v10 carga valores por default_get; aprovechamos get_values()."""
            res = super(VerifactuBaseConfigSettings, self).default_get(fields_list)
            vals = self.get_values()  # ya compone desde singleton/licencia/adjunto
            # Devolvemos SOLO los campos pedidos por la vista
            for k in list(vals.keys()):
                if k not in fields_list:
                    vals.pop(k, None)
            res.update(vals)
            return res

        def execute(self):
            """v10 guarda por execute(); persistimos y dejamos que el super haga su flujo."""
            self.set_values()
            return super(VerifactuBaseConfigSettings, self).execute()

        # Acciones puente v10
        def action_test_certificate(self):
            return self.env['verifactu.endpoint.config'].sudo().get_singleton_record().action_test_certificate()

        def action_reset_certificate(self):
            return self.env['verifactu.endpoint.config'].sudo().get_singleton_record().action_reset_certificate()

        def save_config(self):
            return self.env['verifactu.endpoint.config'].sudo().get_singleton_record().save_config()
