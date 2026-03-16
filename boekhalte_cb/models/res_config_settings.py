# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    cb_config_id = fields.Many2one(
        'cb.config',
        string='Actieve CB Configuratie',
        config_parameter='boekhalte_cb.default_config_id'
    )
