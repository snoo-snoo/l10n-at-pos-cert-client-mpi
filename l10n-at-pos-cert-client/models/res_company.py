# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
import requests
import json

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'
    
    # POS Certification Configuration
    pos_cert_enabled = fields.Boolean(
        string='POS Certification Enabled',
        default=False,
        help='Enable POS certification for this company'
    )
    
    pos_cert_admin_url = fields.Char(
        string='Admin Module URL',
        help='URL of the admin module instance (e.g., http://admin:8069)'
    )
    
    pos_cert_api_key = fields.Char(
        string='API Key',
        help='API key for authentication with admin module'
    )
    
    pos_cert_client_url = fields.Char(
        string='Client Instance URL',
        help='URL of this client instance for admin module'
    )
    
    pos_cert_webhook_url = fields.Char(
        string='Webhook URL',
        help='URL for receiving status updates from admin module'
    )
    
    # Subscription status fields
    pos_cert_status = fields.Selection([
        ('inactive', 'Inactive'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('expired', 'Expired')
    ], string='Subscription Status', default='inactive', compute='_compute_pos_cert_status', store=True)
    
    pos_cert_selected_plan_id = fields.Integer(
        string='Selected Plan ID',
        help='ID of the selected subscription plan from admin module'
    )
    
    pos_cert_selected_plan_name = fields.Char(
        string='Selected Plan Name',
        help='Name of the selected subscription plan'
    )
    
    pos_cert_selected_plan_price = fields.Float(
        string='Selected Plan Price',
        help='Price of the selected subscription plan'
    )
    
    @api.depends('pos_cert_enabled')
    def _compute_pos_cert_status(self):
        """Compute subscription status based on enabled flag"""
        for company in self:
            if company.pos_cert_enabled:
                company.pos_cert_status = 'active'
            else:
                company.pos_cert_status = 'inactive'
    
    def get_available_subscription_plans(self):
        """Get available subscription plans from admin module and create local products"""
        try:
            if not self.pos_cert_api_key:
                _logger.warning('No API key configured for company %s', self.id)
                return {'success': False, 'error': 'No API key configured'}
            
            if not self.pos_cert_admin_url:
                _logger.warning('No admin URL configured for company %s', self.id)
                return {'success': False, 'error': 'No admin URL configured'}
            
            # Make API call to admin module
            api_url = f"{self.pos_cert_admin_url}/api/get_plan"
            headers = {
                'Authorization': f'Bearer {self.pos_cert_api_key}',
                'Content-Type': 'application/json'
            }
            
            _logger.info('Fetching available plans from: %s', api_url)
            
            response = requests.get(api_url, headers=headers, timeout=30)
            _logger.info('Received plans response: %s', response.json())
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    plans = data.get('plans', [])
                    
                    # Create local service products for each plan if they don't exist
                    for plan in plans:
                        self._create_or_update_local_product(plan)
                    
                    _logger.info('Successfully processed %s plans and created/updated local products', len(plans))
                    return data
                else:
                    _logger.error('Failed to get available plans: %s', data.get('error'))
                    return {'success': False, 'error': data.get('error')}
            else:
                _logger.error('HTTP error %s: %s', response.status_code, response.text)
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            _logger.error('Unexpected error getting available plans: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    def _create_or_update_local_product(self, plan_data):
        """Create or update a local service product based on plan data"""
        try:
            admin_plan_id = plan_data.get('id')
            plan_name = plan_data.get('name')
            plan_price = plan_data.get('list_price', 0.0)
            plan_code = plan_data.get('default_code', '')
            
            # Look for existing product with the same plan ID or name
            existing_product = self.env['product.template'].search([
                ('is_pos_subscription_product', '=', True),
                '|',
                ('default_code', '=', plan_code),
                ('name', '=', plan_name)
            ], limit=1)
            
            if existing_product:
                # Update existing product
                existing_product.write({
                    'name': plan_name,
                    'list_price': plan_price,
                    'default_code': plan_code,
                    'is_pos_subscription_product': True,
                    'type': 'service',
                    'sale_ok': True,
                    'purchase_ok': False,
                    'admin_plan_id': admin_plan_id,  # Store admin plan ID
                })
                _logger.info('Updated existing product: %s (ID: %s, Admin Plan ID: %s)', plan_name, existing_product.id, admin_plan_id)
            else:
                # Create new product
                new_product = self.env['product.template'].create({
                    'name': plan_name,
                    'list_price': plan_price,
                    'default_code': plan_code,
                    'is_pos_subscription_product': True,
                    'type': 'service',
                    'sale_ok': True,
                    'purchase_ok': False,
                    'categ_id': self.env.ref('product.product_category_all').id,
                    'admin_plan_id': admin_plan_id,  # Store admin plan ID
                })
                _logger.info('Created new product: %s (ID: %s, Admin Plan ID: %s)', plan_name, new_product.id, admin_plan_id)
                
        except Exception as e:
            _logger.error('Error creating/updating local product for plan %s: %s', plan_data.get('name'), str(e))
    
    def action_select_subscription_plan(self):
        """Action to select subscription plan from available plans"""
        try:
            # Get available plans
            plans_result = self.get_available_subscription_plans()
            
            if not plans_result.get('success'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': f'Failed to get available plans: {plans_result.get("error")}',
                        'type': 'danger',
                    }
                }
            
            plans = plans_result.get('plans', [])
            if not plans:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'No Plans Available',
                        'message': 'No subscription plans are currently available.',
                        'type': 'warning',
                    }
                }
            
            # Open plan selection wizard
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'pos_cert_plan_selection_wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_company_id': self.id,
                    'default_available_plans': json.dumps(plans),
                }
            }
            
        except Exception as e:
            _logger.error('Error in action_select_subscription_plan: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Unexpected error: {str(e)}',
                    'type': 'danger',
                }
            } 