from odoo import models, fields


class VerifactuStatusLog(models.Model):
    _name = "verifactu.status.log"
    _description = "Histórico de cambios de estado VeriFactu"
    _order = "date desc"

    invoice_id = fields.Many2one(
        "account.move",
        string="Factura",
        required=True,
        ondelete="cascade",
    )
    status = fields.Selection(
        selection=lambda self: self.env['account.move']._fields['verifactu_status'].selection,
        string="Estado",
        required=True,
    )
    date = fields.Datetime(
        string="Fecha",
        default=fields.Datetime.now,
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Usuario",
        default=lambda self: self.env.user,
    )
    notes = fields.Text(
        string="Notas (opcional)",
        help="Mensaje complementario sobre el cambio de estado.",
    )
