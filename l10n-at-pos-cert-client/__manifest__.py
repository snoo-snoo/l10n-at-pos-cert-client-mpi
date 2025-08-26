# -*- coding: utf-8 -*-

{
    'name': 'Austrian POS RKSV Compliance Client',
    'version': '1.0.0',
    'category': 'Point of Sale',
    'summary': 'RKSV compliance for Austrian Point of Sale',
    'description': """
        This module extends the Point of Sale receipt template to include
        RKSV (Austrian Cash Register Security Regulation) compliance data.
        
        Features:
        - Extended receipt template with RKSV compliance section
        - Integration with pos.receipt model for response data
        - Proper styling for receipt printing
        - Support for offline/error states
    """,
    'author': 'MPI',
    'website': 'https://www.mpi.com',
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