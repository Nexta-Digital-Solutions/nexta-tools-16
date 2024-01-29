# -*- coding: utf-8 -*-
# (c) 2024 Nexta - Jaume Basiero <jbasiero@nextads.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/a

from odoo import models, fields, api, _
from odoo.tools import float_is_zero

class AccountMove(models.Model):
    _inherit = 'account.move'

    partner_ref = fields.Char(string="Albarán de proveedor", required=False, compute="_compute_partner_ref")
    partner_reference = fields.Char(string="Albarán de proveedor", required=False)

    @api.depends('picking_ids.partner_ref')
    def _compute_partner_ref(self):
        for record in self:
            if record.picking_ids and any(picking.partner_ref for picking in record.picking_ids):
                partner_refs = [picking.partner_ref for picking in record.picking_ids if picking.partner_ref]
                record.partner_ref = ', '.join(partner_refs) if partner_refs else False
            else:
                record.partner_ref = False



    @api.model
    def _get_first_invoice_fields(self, invoice):
        res = super(AccountMove, self)._get_first_invoice_fields(invoice)
        res["partner_reference"] = invoice.partner_ref or ""
        return res

    def do_merge(
            self, keep_references=True, date_invoice=False, remove_empty_invoice_lines=True
    ):
        """
        To merge similar type of account invoices.
        Invoices will only be merged if:
        * Account invoices are in draft
        * Account invoices belong to the same partner
        * Account invoices are have same company, partner, address, currency,
          journal, currency, salesman, account, type
        Lines will only be merged if:
        * Invoice lines are exactly the same except for the quantity and unit

         @param self: The object pointer.
         @param keep_references: If True, keep reference of original invoices

         @return: new account invoice id

        """

        # compute what the new invoices should contain
        new_invoices = {}
        seen_origins = {}
        seen_client_refs = {}

        sum_fields = self._get_sum_fields()

        for account_invoice in self._get_draft_invoices():
            invoice_key = self.make_key(account_invoice, self._get_invoice_key_cols())
            new_invoice = new_invoices.setdefault(invoice_key, ({}, []))
            origins = seen_origins.setdefault(invoice_key, set())
            client_refs = seen_client_refs.setdefault(invoice_key, set())
            new_invoice[1].append(account_invoice.id)
            invoice_infos = new_invoice[0]
            if not invoice_infos:
                invoice_infos.update(self._get_first_invoice_fields(account_invoice))
                origins.add(account_invoice.invoice_origin)
                client_refs.add(account_invoice.payment_reference)
                if not keep_references:
                    invoice_infos.pop("name")
            else:
                if (
                        account_invoice.name
                        and keep_references
                        and invoice_infos.get("name") != account_invoice.name
                ):
                    invoice_infos["name"] = (
                            (invoice_infos["name"] or "") + " " + account_invoice.name
                    )
                if (
                        account_invoice.invoice_origin
                        and account_invoice.invoice_origin not in origins
                ):
                    invoice_infos["invoice_origin"] = (
                            (invoice_infos["invoice_origin"] or "")
                            + " "
                            + account_invoice.invoice_origin
                    )
                    origins.add(account_invoice.invoice_origin)
                if (
                        account_invoice.payment_reference
                        and account_invoice.payment_reference not in client_refs
                ):
                    invoice_infos["payment_reference"] = (
                            (invoice_infos["payment_reference"] or "")
                            + " "
                            + account_invoice.payment_reference
                    )
                    client_refs.add(account_invoice.payment_reference)

                if (
                        account_invoice.partner_ref
                        and account_invoice.partner_ref
                ):
                    invoice_infos["partner_reference"] = invoice_infos.get("partner_reference") + ", " + str(
                        account_invoice.partner_ref)

            for invoice_line in account_invoice.invoice_line_ids:
                line_key = self.make_key(
                    invoice_line, self._get_invoice_line_key_cols()
                )
                o_line = invoice_infos["invoice_line_ids"].setdefault(line_key, {})

                if o_line:
                    # merge the line with an existing line
                    for sum_field in sum_fields:
                        if sum_field in invoice_line._fields:
                            sum_val = invoice_line[sum_field]
                            if isinstance(sum_val, numbers.Number):
                                o_line[sum_field] += sum_val
                else:
                    # append a new "standalone" line
                    o_line.update(self._get_invoice_line_vals(invoice_line))

        allinvoices = []
        allnewinvoices = []
        invoices_info = {}
        old_invoices = self.env["account.move"]
        qty_prec = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        for invoice_key, (invoice_data, old_ids) in new_invoices.items():
            # skip merges with only one invoice
            if len(old_ids) < 2:
                allinvoices += old_ids or []
                continue

            if remove_empty_invoice_lines:
                invoice_data["invoice_line_ids"] = [
                    (0, 0, value)
                    for value in invoice_data["invoice_line_ids"].values()
                    if not float_is_zero(value["quantity"], precision_digits=qty_prec)
                ]
            else:
                invoice_data["invoice_line_ids"] = [
                    (0, 0, value) for value in invoice_data["invoice_line_ids"].values()
                ]

            if date_invoice:
                invoice_data["invoice_date"] = date_invoice

            # create the new invoice
            newinvoice = self.with_context(is_merge=True).create(invoice_data)
            invoices_info.update({newinvoice.id: old_ids})
            allinvoices.append(newinvoice.id)
            allnewinvoices.append(newinvoice)
            # cancel old invoices
            old_invoices = self.env["account.move"].browse(old_ids)
            old_invoices.with_context(is_merge=True).button_cancel()
        self.merge_callback(invoices_info, old_invoices)
        return invoices_info
