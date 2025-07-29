# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
import json
import requests

_logger = logging.getLogger(__name__)


class PosCertPlanSelectionWizard(models.TransientModel):
    _name = 'pos_cert_plan_selection_wizard'
    _description = 'POS Certification Subscription Wizard'
    
    company_id = fields.Many2one('res.company', string='Company', required=True)
    
    def _subscribe(self):
        """Call the admin module's /api/subscribe endpoint"""
        try:
            if not self.company_id.pos_cert_admin_url:
                _logger.warning('No admin URL configured for company %s', self.company_id.id)
                return {'success': False, 'error': 'No admin URL configured'}
            
            if not self.company_id.pos_cert_api_key:
                _logger.warning('No API key configured for company %s', self.company_id.id)
                return {'success': False, 'error': 'No API key configured'}
            
            # Generate webhook URL for this client instance
            webhook_url = self._generate_webhook_url()
            if not webhook_url:
                return {'success': False, 'error': 'Failed to generate webhook URL'}
            
            # Prepare subscription data
            subscription_data = {
                'company_name': self.company_id.name,
                'company_id': self.company_id.id,  # Add company ID
                'webhook_base_url': webhook_url,  # Send only the base URL
            }
            
            # Make API call to admin module
            api_url = f"{self.company_id.pos_cert_admin_url}/api/subscribe"
            headers = {
                'Authorization': f'Bearer {self.company_id.pos_cert_api_key}',
                'Content-Type': 'application/json'
            }
            
            _logger.info('Calling admin subscribe API: %s', api_url)
            _logger.info('Subscription data: %s', subscription_data)
            
            response = requests.post(
                api_url, 
                json=subscription_data, 
                headers=headers, 
                timeout=30
            )
            
            _logger.info('Admin API response status: %s', response.status_code)
            _logger.info('Admin API response: %s', response.text)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    _logger.info('Successfully created subscription: %s', data.get('subscription_id'))
                    return data
                else:
                    _logger.error('Failed to create subscription: %s', data.get('error'))
                    return {'success': False, 'error': data.get('error')}
            else:
                _logger.error('HTTP error %s: %s', response.status_code, response.text)
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            _logger.error('Unexpected error calling admin subscribe API: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    def _generate_webhook_url(self):
        """Generate base URL for this client instance"""
        try:
            # Get the base URL for this Odoo instance
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            if not base_url:
                _logger.error('No base URL configured for this Odoo instance')
                return False
            
            # Return only the base URL - admin module will construct specific endpoints
            _logger.info('Generated base URL for webhooks: %s', base_url)
            
            return base_url
            
        except Exception as e:
            _logger.error('Error generating base URL: %s', str(e))
            return False
    
    def action_subscribe(self):
        """Subscribe to POS certification service"""
        self.ensure_one()
        
        try:
            # Call admin module to create subscription
            subscription_result = self._subscribe()
            
            if not subscription_result.get('success'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Subscription Error',
                        'message': f'Failed to create subscription: {subscription_result.get("error")}',
                        'type': 'danger',
                    }
                }
            
            # Update company with subscription information and set status to pending
            self.company_id.write({
                'pos_cert_status': 'pending',  # Set to pending until payment is received
            })
            
            _logger.info('Created subscription for company %s with pending status', self.company_id.name)
            
            # Get portal URL for payment
            portal_url = subscription_result.get('portal_url')
            if portal_url:
                _logger.info('Redirecting to payment portal: %s', portal_url)
                
                # Close the wizard and redirect to payment portal
                return {
                    'type': 'ir.actions.act_url',
                    'url': portal_url,
                    'target': 'new',
                }
            else:
                # Close the wizard and show success message
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Subscription Created',
                        'message': 'Successfully created POS certification subscription. Please contact support for payment.',
                        'type': 'success',
                    }
                }
            
        except Exception as e:
            _logger.error('Error creating subscription: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to create subscription: {str(e)}',
                    'type': 'danger',
                }
            } 