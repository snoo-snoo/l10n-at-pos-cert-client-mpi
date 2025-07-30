# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
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
    
    # Fiskaly status (received from admin via webhook)
    l10n_at_fiskaly_organization_status = fields.Selection([
        ('not_created', 'Not Created'),
        ('creating', 'Creating'),
        ('created', 'Created'),
        ('failed', 'Failed')
    ], string="Fiskaly Organization Status", default='not_created')
    l10n_at_fiskaly_organization_error = fields.Text(string="Fiskaly Organization Error", help="Error message if organization creation failed")
    
    def create_fiskaly_organization(self):
        """Create Fiskaly organization via admin endpoint"""
        self.ensure_one()
        
        try:
            if self.pos_cert_status != 'active':
                raise UserError(_("Subscription must be active to create Fiskaly organization"))
            
            if not self.pos_cert_admin_url or not self.pos_cert_api_key:
                raise UserError(_("Admin URL and API key must be configured"))
            
            if self.l10n_at_fiskaly_organization_status == 'created':
                raise UserError(_("Fiskaly organization already created"))
            
            # Update status to creating
            self.write({'l10n_at_fiskaly_organization_status': 'creating'})
            
            # Prepare company data
            company_data = {
                'name': self.name,
                'street': self.street,
                'street2': self.street2,
                'zip': self.zip,
                'city': self.city,
                'country_code': self.country_id.code if self.country_id else 'AUT',
                'vat': self.vat,
            }
            
            # Call admin endpoint
            url = f"{self.pos_cert_admin_url}/api/pos_cert/create_fiskaly_organization"
            payload = {
                'company_data': company_data,
            }
            
            _logger.info('Calling admin endpoint to create Fiskaly organization: %s', url)
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.pos_cert_api_key}'
            }
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=60
            )
            
            result = response.json()
            
            if result.get('success'):
                self.write({
                    'l10n_at_fiskaly_organization_status': 'created',
                    'l10n_at_fiskaly_organization_error': False,
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': f'Fiskaly organization created successfully: {result.get("organization_id")}',
                        'type': 'success',
                    }
                }
            else:
                self.write({
                    'l10n_at_fiskaly_organization_status': 'failed',
                    'l10n_at_fiskaly_organization_error': result.get('error', 'Unknown error'),
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': f'Failed to create Fiskaly organization: {result.get("error")}',
                        'type': 'danger',
                    }
                }
                
        except Exception as e:
            _logger.error('Error creating Fiskaly organization: %s', str(e))
            self.write({
                'l10n_at_fiskaly_organization_status': 'failed',
                'l10n_at_fiskaly_organization_error': str(e),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error creating Fiskaly organization: {str(e)}',
                    'type': 'danger',
                }
            }
    
    def cancel_plan(self):
        """Cancel the current subscription plan and clear subscription fields"""
        self.ensure_one()
        
        try:
            _logger.info('Cancelling plan for company %s (ID: %s)', self.name, self.id)
            
            # Clear subscription and plan fields
            self.write({
                'pos_cert_status': 'inactive',
                'l10n_at_fiskaly_organization_status': 'not_created',
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