# -*- coding: utf-8 -*-
{
    'name': 'De Boekhalte CB',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Products',
    'summary': 'Importeer boeken van De Boekhalte CB via FTP (ONIX/CSV)',
    'description': """
        De Boekhalte CB Integratie voor Odoo 17
        ================================================
        - FTP-verbinding met CB configureren
        - Boeken automatisch importeren als producten
        - NUR-codes vertalen naar Odoo-categorieën
        - Voorraad en levertijden dagelijks synchroniseren
        - Prijsupdates verwerken
        - Volledige importlogs bijhouden
    """,
    'author': 'Jouw Bedrijf',
    'depends': [
        'product',
        'stock',
        'purchase',
        'sale_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/cb_nur_codes.xml',
        'data/cb_cron.xml',
        'views/cb_config_views.xml',
        'views/cb_import_log_views.xml',
        'views/cb_product_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/cb_import_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
