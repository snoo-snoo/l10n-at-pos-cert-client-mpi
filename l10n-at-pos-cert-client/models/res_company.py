# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
import requests
import json

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    # POS Certification Configuration
    pos_cert_admin_url = fields.Char(
        string='Admin Module URL',
        help='URL of the admin module instance (e.g., http://admin:8069)'
    )
    
    pos_cert_api_key = fields.Char(
        string='API Key',
        help='API key for authentication with admin module'
    )
    
    # Subscription status fields
    pos_cert_status = fields.Selection([
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired')
    ], string='Subscription Status', default='inactive')
    
    def cancel_plan(self):
        """Cancel the current subscription plan and clear subscription fields"""
        self.ensure_one()
        
        try:
            _logger.info('Cancelling plan for company %s (ID: %s)', self.name, self.id)
            
            # Clear subscription and plan fields
            self.write({
                'pos_cert_status': 'inactive',
            })
            
            _logger.info('Successfully cancelled plan for company %s', self.name)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Plan Cancelled',
                    'message': f'Successfully cancelled subscription plan for {self.name}.',
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error('Error cancelling plan for company %s: %s', self.name, str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to cancel plan: {str(e)}',
                    'type': 'danger',
                }
            }
    
    def action_subscribe_to_pos_cert(self):
        """Action to subscribe to POS certification service"""
        try:
            # Open subscription wizard
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'pos_cert_plan_selection_wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_company_id': self.id,
                }
            }
            
        except Exception as e:
            _logger.error('Error in action_subscribe_to_pos_cert: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Unexpected error: {str(e)}',
                    'type': 'danger',
                }
            } 