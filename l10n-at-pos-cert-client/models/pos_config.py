# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import requests
import json

_logger = logging.getLogger(__name__)


class PosConfig(models.Model):
    _inherit = 'pos.config'
    
    # POS Certification fields
    pos_cert_status = fields.Selection([
        ('inactive', 'Inactive'),
        ('pending', 'Pending'),
        ('active', 'Active')
    ], string='Cash Register Status', default='inactive', help='Status of the cash register registration')
    
    pos_cert_registration_date = fields.Datetime(
        string='Registration Date',
        help='Date when the cash register was registered'
    )
    
    pos_cert_subscription_id = fields.Integer(
        string='POS Certification Subscription ID',
        help='Subscription order ID from admin module for this cash register'
    )
    
    # Cash Register fields
    pos_cert_cash_register_id = fields.Char(
        string='Cash Register ID',
        help='Cash register ID'
    )
    
    pos_cert_cash_register_status = fields.Selection([
        ('CREATED', 'Created'),
        ('INITIALIZED', 'Initialized'),
        ('DECOMMISSIONED', 'Decommissioned'),
        ('DEFECTIVE', 'Defective'),
        ('OUTAGE', 'Outage')
    ], string='Cash Register Status', default='CREATED', help='Status of the cash register')
    
    def action_register_cash_register(self):
        """Register the cash register with the admin module"""
        self.ensure_one()
        
        try:
            _logger.info('Registering cash register for POS config: %s (ID: %s)', self.name, self.id)
            
            # Get company and validate configuration
            company = self.company_id
            if not company.pos_cert_admin_url:
                raise UserError(_("Admin URL not configured. Please configure the admin URL in company settings."))
            
            if not company.pos_cert_api_key:
                raise UserError(_("API key not configured. Please configure the API key in company settings."))
            
            # Call admin module to register cash register
            result = self._call_admin_register_api()
            
            if result.get('success'):
                # Don't update the record here - let the webhook handle it
                _logger.info('Successfully registered cash register: %s', self.name)
                
                # Redirect to payment portal if URL is provided
                portal_url = result.get('portal_url')
                if portal_url:
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
                            'title': 'Registration Successful',
                            'message': 'Cash register registered successfully. Please contact support for payment.',
                            'type': 'success',
                        }
                    }
            else:
                error_msg = result.get('error', 'Unknown error occurred')
                _logger.error('Failed to register cash register: %s', error_msg)
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Registration Failed',
                        'message': f'Failed to register cash register: {error_msg}',
                        'type': 'danger',
                    }
                }
                
        except Exception as e:
            _logger.error('Error registering cash register: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error registering cash register: {str(e)}',
                    'type': 'danger',
                }
            }
    
    def action_create_cash_register(self):
        """Create cash register via admin module"""
        self.ensure_one()
        
        try:
            _logger.info('Creating cash register for POS config: %s (ID: %s)', self.name, self.id)
            
            # Get company and validate configuration
            company = self.company_id
            if not company.pos_cert_admin_url:
                raise UserError(_("Admin URL not configured. Please configure the admin URL in company settings."))
            
            if not company.pos_cert_api_key:
                raise UserError(_("API key not configured. Please configure the API key in company settings."))
            
            # Call admin module to create cash register
            result = self._call_admin_create_cash_register_api()
            
            if result.get('success'):
                # Update the record with cash register information
                self.write({
                    'pos_cert_cash_register_id': result.get('cash_register_id'),
                    'pos_cert_cash_register_status': result.get('cash_register_status', 'REGISTERED'),
                })
                
                _logger.info('Successfully created cash register: %s', result.get('cash_register_id'))
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Cash Register Created',
                        'message': f'Cash register created successfully with ID: {result.get("cash_register_id")}',
                        'type': 'success',
                    }
                }
            else:
                error_msg = result.get('error', 'Unknown error occurred')
                _logger.error('Failed to create cash register: %s', error_msg)
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Creation Failed',
                        'message': f'Failed to create cash register: {error_msg}',
                        'type': 'danger',
                    }
                }
                
        except Exception as e:
            _logger.error('Error creating cash register: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error creating cash register: {str(e)}',
                    'type': 'danger',
                }
            }
    
    def _call_admin_register_api(self):
        """Call the admin module's register cash register endpoint"""
        try:
            company = self.company_id
            
            # Prepare registration data
            registration_data = {
                'pos_config_id': self.id,
                'pos_config_name': self.name,
                'company_name': company.name,
                'company_id': company.id,
            }
            
            # Make API call to admin module
            api_url = f"{company.pos_cert_admin_url}/api/pos_cert/register_cash_register"
            headers = {
                'Authorization': f'Bearer {company.pos_cert_api_key}',
                'Content-Type': 'application/json'
            }
            
            _logger.info('Calling admin register API: %s', api_url)
            _logger.info('Registration data: %s', registration_data)
            
            response = requests.post(
                api_url, 
                json=registration_data, 
                headers=headers, 
                timeout=30
            )
            
            _logger.info('Admin API response status: %s', response.status_code)
            _logger.info('Admin API response: %s', response.text)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    _logger.info('Successfully registered cash register: %s', data.get('subscription_id'))
                    return data
                else:
                    _logger.error('Failed to register cash register: %s', data.get('error'))
                    return {'success': False, 'error': data.get('error')}
            else:
                _logger.error('HTTP error %s: %s', response.status_code, response.text)
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            _logger.error('Unexpected error calling admin register API: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    def _call_admin_create_cash_register_api(self):
        """Call the admin module's create cash register endpoint"""
        try:
            company = self.company_id
            
            # Prepare cash register creation data
            creation_data = {
                'pos_config_id': self.id,
                'pos_config_name': self.name,
                'company_name': company.name,
                'company_id': company.id,
            }
            
            # Make API call to admin module
            api_url = f"{company.pos_cert_admin_url}/api/pos_cert/create_cash_register"
            headers = {
                'Authorization': f'Bearer {company.pos_cert_api_key}',
                'Content-Type': 'application/json'
            }
            
            _logger.info('Calling admin create cash register API: %s', api_url)
            _logger.info('Creation data: %s', creation_data)
            
            response = requests.post(
                api_url, 
                json=creation_data, 
                headers=headers, 
                timeout=30
            )
            
            _logger.info('Admin API response status: %s', response.status_code)
            _logger.info('Admin API response: %s', response.text)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    _logger.info('Successfully created cash register: %s', data.get('cash_register_id'))
                    return data
                else:
                    _logger.error('Failed to create cash register: %s', data.get('error'))
                    return {'success': False, 'error': data.get('error')}
            else:
                _logger.error('HTTP error %s: %s', response.status_code, response.text)
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            _logger.error('Unexpected error calling admin create cash register API: %s', str(e))
            return {'success': False, 'error': str(e)} 