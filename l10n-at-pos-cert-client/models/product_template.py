# -*- coding: utf-8 -*-

from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    is_pos_subscription_product = fields.Boolean(
        string='POS Subscription Product',
        help='Indicates if this product is used for POS certification subscriptions'
    )
    
    admin_plan_id = fields.Integer(
        string='Admin Plan ID',
        help='ID of the corresponding product in the admin module'
    ) 