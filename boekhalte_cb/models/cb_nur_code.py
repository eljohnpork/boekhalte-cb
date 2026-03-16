# -*- coding: utf-8 -*-
from odoo import models, fields, api


class CbNurCode(models.Model):
    _name = 'cb.nur.code'
    _description = 'NUR Code (Nederlandse Uniforme Rubrieksindeling)'
    _order = 'code'

    code = fields.Char(string='NUR Code', required=True, index=True)
    name = fields.Char(string='Omschrijving', required=True)
    parent_id = fields.Many2one('cb.nur.code', string='Hoofdcategorie')
    child_ids = fields.One2many('cb.nur.code', 'parent_id', string='Subcategorieën')
    product_categ_id = fields.Many2one(
        'product.category',
        string='Odoo Productcategorie',
        help='Koppel deze NUR-code aan een bestaande productcategorie'
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'NUR-code moet uniek zijn!'),
    ]
