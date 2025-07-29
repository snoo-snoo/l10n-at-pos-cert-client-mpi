{
    'name': 'POS Certification - Client',
    'version': '1.0',
    'category': 'Point of Sale',
    'summary': 'POS Certification Module for Client',
    'description': """
        POS Certification Module for Client Instance
        This module handles the fiscal requirements for Point of Sale systems.
        Provides integration with admin module for subscription management.
    """,
    'author': 'trananhnguyen97',
    'website': 'https://www.mpi.com',
    'depends': [
        'base',
        'point_of_sale',
        'sale',
        'payment',
    ],
    'external_dependencies': {
        'python': ['requests'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/res_company_views.xml',
        'views/pos_cert_plan_selection_wizard_views.xml',
    ],
    'demo': [],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
} 