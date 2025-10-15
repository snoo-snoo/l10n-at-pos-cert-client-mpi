# -*- coding: utf-8 -*-

{
    'name': 'RKSV-Modul für österreichische Registrierkassen',
    'version': '19.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'RKSV-Modul für österreichische Registrierkassen',
    'description': """
        Dieses Modul implementiert die gesetzlichen Anforderungen für Registrierkassen in Österreich (RKSV).
        
        Funktionen:
        - Digitale Signatur von Belegen
        - Erstellung und Export von DEP-7 Dateien
        - Integration mit dem Odoo Point of Sale
        - Verwaltung von Zertifikaten und Schlüsseln
        - Automatische Sicherung der Daten
        
        Das Modul erfüllt alle Anforderungen der Registrierkassensicherheitsverordnung (RKSV).
    """,
    'images': ['icon.png', 'static/description/icon.png'],
    'author': 'MPI GmbH',
    'website': 'https://www.mpi-erp.at',
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
