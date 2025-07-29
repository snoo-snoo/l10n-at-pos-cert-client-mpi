# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
import json
import requests

_logger = logging.getLogger(__name__)


class PosCertPlanSelectionWizard(models.TransientModel):
    _name = 'pos_cert_plan_selection_wizard'
    _description = 'POS Certification Plan Selection Wizard'
    
    company_id = fields.Many2one('res.company', string='Company', required=True)
    selected_plan_id = fields.Many2one('product.template', string='Select Plan', 
                                      domain=[('is_pos_subscription_product', '=', True), ('active', '=', True)])
    
    @api.onchange('selected_plan_id')
    def _onchange_selected_plan_id(self):
        """Update display when plan is selected"""
        if self.selected_plan_id:
            _logger.info('Selected plan: %s (ID: %s)', self.selected_plan_id.name, self.selected_plan_id.id)
    
    def _subscribe(self, plan_data):
        """Call the admin module's /api/subscribe endpoint"""
        try:
            if not self.company_id.pos_cert_admin_url:
                _logger.warning('No admin URL configured for company %s', self.company_id.id)
                return {'success': False, 'error': 'No admin URL configured'}
            
            if not self.company_id.pos_cert_api_key:
                _logger.warning('No API key configured for company %s', self.company_id.id)
                return {'success': False, 'error': 'No API key configured'}
            
            # Use admin plan ID if available, otherwise fall back to client product ID
            admin_plan_id = self.selected_plan_id.admin_plan_id or self.selected_plan_id.id
            
            # Prepare subscription data
            subscription_data = {
                'company_name': self.company_id.name,
                'product_id': admin_plan_id,  # Use admin plan ID
                'client_url': self.company_id.pos_cert_client_url,
                'webhook_url': self.company_id.pos_cert_webhook_url,
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
    
    def action_select_plan(self):
        """Select the chosen plan and create subscription"""
        self.ensure_one()
        
        try:
            if not self.selected_plan_id:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'No Plan Selected',
                        'message': 'Please select a plan before proceeding.',
                        'type': 'warning',
                    }
                }
            
            # Call admin module to create subscription
            subscription_result = self._subscribe({})
            
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
            
            # Update company with selected plan
            self.company_id.write({
                'pos_cert_selected_plan_id': self.selected_plan_id.id,
                'pos_cert_selected_plan_name': self.selected_plan_id.name,
                'pos_cert_selected_plan_price': self.selected_plan_id.list_price,
            })
            
            _logger.info('Selected plan for company %s: %s (ID: %s, Price: %s)', 
                        self.company_id.name, self.selected_plan_id.name, 
                        self.selected_plan_id.id, self.selected_plan_id.list_price)
            
            # Get portal URL for payment
            portal_url = subscription_result.get('portal_url')
            if portal_url:
                _logger.info('Redirecting to payment portal: %s', portal_url)
                
                # Return action to redirect to payment portal
                return {
                    'type': 'ir.actions.act_url',
                    'url': portal_url,
                    'target': 'new',
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Plan Selected',
                        'message': f'Successfully selected plan: {self.selected_plan_id.name}. Please contact support for payment.',
                        'type': 'success',
                    }
                }
            
        except Exception as e:
            _logger.error('Error selecting plan: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to select plan: {str(e)}',
                    'type': 'danger',
                }
            } 