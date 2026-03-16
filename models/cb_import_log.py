# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class CbImportLog(models.Model):
    _name = 'cb.import.log'
    _description = 'CB Import Log'
    _order = 'create_date desc'
    _rec_name = 'create_date'

    config_id = fields.Many2one('cb.config', string='Configuratie', ondelete='cascade')
    sync_type = fields.Selection([
        ('catalog', 'Catalogus'),
        ('stock', 'Voorraad (BHDART)'),
        ('orders', 'Orders (UITOPD/NUITOP)'),
        ('invoices', 'Facturen (DVFACBUBL)'),
        ('full', 'Volledig'),
    ], string='Type Sync', required=True)
    state = fields.Selection([
        ('running', 'Bezig...'),
        ('done', 'Voltooid'),
        ('error', 'Fout'),
    ], string='Status', default='running')

    products_created = fields.Integer(string='Aangemaakt', default=0)
    products_updated = fields.Integer(string='Bijgewerkt', default=0)
    errors = fields.Integer(string='Fouten', default=0)
    message = fields.Text(string='Bericht')
    duration = fields.Float(string='Duur (sec)', readonly=True)

    log_lines = fields.One2many('cb.import.log.line', 'log_id', string='Log regels')

    def name_get(self):
        result = []
        for rec in self:
            sync_label = dict(self.fields_get(['sync_type'])['sync_type']['selection']).get(
                rec.sync_type, rec.sync_type
            )
            name = '%s - %s' % (
                sync_label,
                rec.create_date.strftime('%d-%m-%Y %H:%M') if rec.create_date else '?'
            )
            result.append((rec.id, name))
        return result


class CbImportLogLine(models.Model):
    _name = 'cb.import.log.line'
    _description = 'CB Import Log Regel'
    _order = 'id desc'

    log_id = fields.Many2one('cb.import.log', string='Log', ondelete='cascade')
    level = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Waarschuwing'),
        ('error', 'Fout'),
    ], default='info')
    message = fields.Text(string='Bericht')
    isbn = fields.Char(string='ISBN/EAN')
