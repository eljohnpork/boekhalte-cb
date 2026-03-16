# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # CB-specifieke velden
    cb_isbn = fields.Char(
        string='ISBN',
        compute='_compute_cb_isbn',
        store=True,
        help='Internationaal Standaard Boeknummer'
    )
    cb_authors = fields.Char(string='Auteur(s)')
    cb_publisher = fields.Char(string='Uitgever')
    cb_nur_code = fields.Char(string='NUR Code')
    cb_nur_name = fields.Char(
        string='NUR Omschrijving',
        compute='_compute_nur_name',
        store=True
    )
    cb_last_sync = fields.Datetime(string='Laatste CB Sync', readonly=True)
    cb_is_book = fields.Boolean(
        string='Is een boek (CB)',
        compute='_compute_is_book',
        store=True
    )

    @api.depends('barcode')
    def _compute_cb_isbn(self):
        for rec in self:
            rec.cb_isbn = rec.barcode or ''

    @api.depends('cb_nur_code')
    def _compute_nur_name(self):
        for rec in self:
            if rec.cb_nur_code:
                nur = self.env['cb.nur.code'].search(
                    [('code', '=', rec.cb_nur_code)], limit=1
                )
                rec.cb_nur_name = nur.name if nur else ''
            else:
                rec.cb_nur_name = ''

    @api.depends('cb_nur_code', 'cb_authors')
    def _compute_is_book(self):
        for rec in self:
            rec.cb_is_book = bool(rec.cb_nur_code or rec.cb_authors)
