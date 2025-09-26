# -*- coding: utf-8 -*-

{
    'name': 'Austrian POS RKSV Compliance Client',
    'version': '18.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'RKSV compliance for Austrian Point of Sale',
    'description': 'static/description/home.html',
    'images': ['static/description/icon.png'],
    'author': 'Ngyuen Tran and Michael Plöckinger',
    'website': 'https://www.mpi-erp.at',
    'repository': 'ssh://git@github.com/snoo-snoo/mpi-l10n-at-pos-cert-client.git#18.0',
    'price': 290.00,
    'currency': 'EUR',
    'depends': [
        'point_of_sale',
        'base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/pos_order_views.xml',
        'views/pos_receipt_views.xml',
        'views/pos_config_views.xml',
        'views/res_company_views.xml',
        'views/pos_cert_dep7_export_wizard_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'l10n-at-pos-cert-client/static/src/**/*',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
