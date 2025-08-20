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
    
    # Organization status (received from admin via webhook)
    l10n_at_organization_status = fields.Selection([
        ('not_created', 'Not Created'),
        ('creating', 'Creating'),
        ('created', 'Created'),
        ('failed', 'Failed')
    ], string="Organization Status", default='not_created')
    l10n_at_organization_error = fields.Text(string="Organization Error", help="Error message if organization creation failed")
    
    # FON Authentication fields
    l10n_at_fon_participant_id = fields.Char(
        string='FON Participant ID',
        help='FON Participant ID (8-12 characters, alphanumeric)'
    )
    l10n_at_fon_user_id = fields.Char(
        string='FON User ID',
        help='FON User ID (5-12 characters)'
    )
    l10n_at_fon_user_pin = fields.Char(
        string='FON User PIN',
        help='FON User PIN (5-128 characters)',
        password=True
    )
    l10n_at_fon_authentication_status = fields.Selection([
        ('unauthenticated', 'Unauthenticated'),
        ('authenticated', 'Authenticated')
    ], string='FON Authentication Status', default='unauthenticated')
    l10n_at_fon_authentication_date = fields.Datetime(
        string='FON Authentication Date',
        help='Date when FON was last authenticated'
    )
    l10n_at_fon_authentication_error = fields.Text(
        string='FON Authentication Error',
        help='Error message if FON authentication failed'
    )
    
    # SCU (Signature Creation Unit) fields
    l10n_at_scu_id = fields.Char(string="SCU ID", help="Signature Creation Unit ID (UUID4)")
    l10n_at_scu_status = fields.Selection([
        ('PENDING', 'Pending'),
        ('CREATED', 'Created'),
        ('INITIALIZED', 'Initialized'),
        ('DECOMMISSIONED', 'Decommissioned'),
        ('OUTAGE', 'Outage'),
        ('DEFECTIVE', 'Defective')
    ], string="SCU Status", default='PENDING')
    l10n_at_scu_error = fields.Text(string="SCU Error", help="Error message if SCU creation failed")
    l10n_at_scu_initialization_error = fields.Text(string="SCU Initialization Error", help="Error message if SCU initialization failed")
    
    def create_organization(self):
        """Create organization via admin endpoint"""
        self.ensure_one()
        
        try:
            if self.pos_cert_status != 'active':
                raise UserError(_("Subscription must be active to create organization"))
            
            if not self.pos_cert_admin_url or not self.pos_cert_api_key:
                raise UserError(_("Admin URL and API key must be configured"))
            
            if self.l10n_at_organization_status == 'created':
                raise UserError(_("Organization already created"))
            
            # Update status to creating
            self.write({'l10n_at_organization_status': 'creating'})
            
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
            url = f"{self.pos_cert_admin_url}/api/pos_cert/create_organization"
            payload = {
                'company_data': company_data,
            }
            
            _logger.info('Calling admin endpoint to create organization: %s', url)
            
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
                    'l10n_at_organization_status': 'created',
                    'l10n_at_organization_error': False,
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': f'Organization created successfully: {result.get("organization_id")}',
                        'type': 'success',
                    }
                }
            else:
                self.write({
                    'l10n_at_organization_status': 'failed',
                    'l10n_at_organization_error': result.get('error', 'Unknown error'),
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': f'Failed to create organization: {result.get("error")}',
                        'type': 'danger',
                    }
                }
                
        except Exception as e:
            _logger.error('Error creating organization: %s', str(e))
            self.write({
                'l10n_at_organization_status': 'failed',
                'l10n_at_organization_error': str(e),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error creating organization: {str(e)}',
                    'type': 'danger',
                }
            }
    
    def action_create_scu(self):
        """Create Signature Creation Unit via admin endpoint"""
        self.ensure_one()
        
        try:
            if self.pos_cert_status != 'active':
                raise UserError(_("Subscription must be active to create SCU"))
            
            if not self.pos_cert_admin_url or not self.pos_cert_api_key:
                raise UserError(_("Admin URL and API key must be configured"))
            
            if self.l10n_at_organization_status != 'created':
                raise UserError(_("Organization must be created before creating SCU"))
            
            # if self.l10n_at_fon_authentication_status != 'authenticated':
            #     raise UserError(_("FON must be authenticated before creating SCU"))
            
            if self.l10n_at_scu_id:
                raise UserError(_("SCU already exists for this company"))
            
            if not self.vat:
                raise UserError(_("VAT ID is required to create SCU"))
            
            # Update status to creating
            self.write({
                'l10n_at_scu_status': 'PENDING',
                'l10n_at_scu_error': False,
            })
            
            # Call admin endpoint
            url = f"{self.pos_cert_admin_url}/api/pos_cert/create_scu"
            payload = {
                'vat_id': self.vat,
            }
            
            _logger.info('Calling admin endpoint to create SCU: %s', url)
            
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
                    'l10n_at_scu_id': result.get('scu_id'),
                    'l10n_at_scu_status': result.get('scu_status', 'PENDING'),
                    'l10n_at_scu_error': False,
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': f'SCU created successfully: {result.get("scu_id")}',
                        'type': 'success',
                    }
                }
            else:
                self.write({
                    'l10n_at_scu_status': 'PENDING',
                    'l10n_at_scu_error': result.get('error', 'Unknown error'),
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': f'Failed to create SCU: {result.get("error")}',
                        'type': 'danger',
                    }
                }
                
        except Exception as e:
            _logger.error('Error creating SCU: %s', str(e))
            self.write({
                'l10n_at_scu_status': 'PENDING',
                'l10n_at_scu_error': str(e),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error creating SCU: {str(e)}',
                    'type': 'danger',
                }
            }
    
    def action_initialize_scu(self):
        """Initialize Signature Creation Unit via admin endpoint"""
        self.ensure_one()
        
        try:
            if self.pos_cert_status != 'active':
                raise UserError(_("Subscription must be active to initialize SCU"))
            
            if not self.pos_cert_admin_url or not self.pos_cert_api_key:
                raise UserError(_("Admin URL and API key must be configured"))
            
            if self.l10n_at_organization_status != 'created':
                raise UserError(_("Organization must be created before initializing SCU"))
            
            if not self.l10n_at_scu_id:
                raise UserError(_("SCU must be created before initializing"))
            
            if self.l10n_at_scu_status == 'INITIALIZED':
                raise UserError(_("SCU is already initialized"))
            
            if self.l10n_at_scu_status in ['DECOMMISSIONED', 'OUTAGE', 'DEFECTIVE']:
                raise UserError(_(f"Cannot initialize SCU in current state: {self.l10n_at_scu_status}"))
            
            # Check FON authentication (show error if not authenticated)
            if self.l10n_at_fon_authentication_status != 'authenticated':
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': 'FON must be authenticated before initializing SCU. Please authenticate FON first.',
                        'type': 'danger',
                    }
                }
            
            # Update initialization error field
            self.write({
                'l10n_at_scu_initialization_error': False,
            })
            
            # Call admin endpoint
            url = f"{self.pos_cert_admin_url}/api/pos_cert/initialize_scu"
            
            _logger.info('Calling admin endpoint to initialize SCU: %s', url)
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.pos_cert_api_key}'
            }
            
            response = requests.post(
                url,
                json={},  # No payload needed for initialization
                headers=headers,
                timeout=60
            )
            
            result = response.json()
            
            if result.get('success'):
                self.write({
                    'l10n_at_scu_status': result.get('scu_status', 'PENDING'),
                    'l10n_at_scu_initialization_error': False,
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': f'SCU initialized successfully: {result.get("message")}',
                        'type': 'success',
                    }
                }
            else:
                self.write({
                    'l10n_at_scu_initialization_error': result.get('error', 'Unknown error'),
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': f'Failed to initialize SCU: {result.get("error")}',
                        'type': 'danger',
                    }
                }
                
        except Exception as e:
            _logger.error('Error initializing SCU: %s', str(e))
            self.write({
                'l10n_at_scu_initialization_error': str(e),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error initializing SCU: {str(e)}',
                    'type': 'danger',
                }
            }
    
    def action_authenticate_fon(self):
        """Authenticate FON via admin endpoint"""
        self.ensure_one()
        
        try:
            if self.pos_cert_status != 'active':
                raise UserError(_("Subscription must be active to authenticate FON"))
            
            if not self.pos_cert_admin_url or not self.pos_cert_api_key:
                raise UserError(_("Admin URL and API key must be configured"))
            
            # Validate that FON credentials are provided
            if not self.l10n_at_fon_participant_id:
                raise UserError(_("FON Participant ID is required"))
            if not self.l10n_at_fon_user_id:
                raise UserError(_("FON User ID is required"))
            if not self.l10n_at_fon_user_pin:
                raise UserError(_("FON User PIN is required"))
            
            # Update status to authenticating
            self.write({
                'l10n_at_fon_authentication_status': 'unauthenticated',
                'l10n_at_fon_authentication_error': False,
            })
            
            # Prepare FON credentials
            fon_credentials = {
                'fon_participant_id': self.l10n_at_fon_participant_id,
                'fon_user_id': self.l10n_at_fon_user_id,
                'fon_user_pin': self.l10n_at_fon_user_pin,
            }
            
            # Call admin endpoint
            url = f"{self.pos_cert_admin_url}/api/pos_cert/authenticate_fon"
            payload = {
                'fon_credentials': fon_credentials,
            }
            
            _logger.info('Calling admin endpoint to authenticate FON: %s', url)
            
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
                    'l10n_at_fon_authentication_status': 'authenticated',
                    'l10n_at_fon_authentication_date': fields.Datetime.now(),
                    'l10n_at_fon_authentication_error': False,
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Success',
                        'message': 'FON authenticated successfully',
                        'type': 'success',
                    }
                }
            else:
                self.write({
                    'l10n_at_fon_authentication_status': 'unauthenticated',
                    'l10n_at_fon_authentication_error': result.get('error', 'Unknown error'),
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Error',
                        'message': f'Failed to authenticate FON: {result.get("error")}',
                        'type': 'danger',
                    }
                }
                
        except Exception as e:
            _logger.error('Error authenticating FON: %s', str(e))
            self.write({
                'l10n_at_fon_authentication_status': 'unauthenticated',
                'l10n_at_fon_authentication_error': str(e),
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error authenticating FON: {str(e)}',
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
                'l10n_at_organization_status': 'not_created',
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