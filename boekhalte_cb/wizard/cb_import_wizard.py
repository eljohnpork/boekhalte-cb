# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class CbImportWizard(models.TransientModel):
    _name = 'cb.import.wizard'
    _description = 'CB Import Wizard'

    config_id = fields.Many2one('cb.config', string='Configuratie', required=True)
    import_type = fields.Selection([
        ('full', 'Volledig (Catalogus + Voorraad + Prijzen)'),
        ('catalog', 'Alleen Catalogus'),
        ('stock', 'Alleen Voorraad & Levertijden'),
        ('prices', 'Alleen Prijzen'),
    ], string='Import Type', default='full', required=True)

    nur_filter = fields.Char(
        string='Filter op NUR-code',
        help='Komma-gescheiden lijst van NUR-codes, bijv: 301,302,340'
    )
    only_new = fields.Boolean(
        string='Alleen nieuwe producten importeren',
        default=False
    )

    state = fields.Selection([
        ('draft', 'Klaar om te importeren'),
        ('done', 'Voltooid'),
    ], default='draft')

    result_message = fields.Text(string='Resultaat', readonly=True)
    log_id = fields.Many2one('cb.import.log', string='Import Log', readonly=True)

    def action_import(self):
        """Voer import uit."""
        self.ensure_one()
        config = self.config_id

        try:
            if self.import_type in ('full', 'catalog'):
                config._sync_catalog()
            if self.import_type in ('full', 'stock'):
                config._sync_stock()
            if self.import_type in ('full', 'prices'):
                config._sync_prices()

            self.write({
                'state': 'done',
                'result_message': _(
                    'Import succesvol afgerond!\n'
                    'Aangemaakt: %d\nBijgewerkt: %d\nFouten: %d'
                ) % (
                    config.last_sync_created,
                    config.last_sync_updated,
                    config.last_sync_errors,
                )
            })

        except Exception as e:
            self.write({
                'state': 'done',
                'result_message': _('Fout tijdens import: %s') % str(e),
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cb.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_view_log(self):
        """Open het import log."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'cb.import.log',
            'view_mode': 'list,form',
            'domain': [('config_id', '=', self.config_id.id)],
            'target': 'current',
        }
