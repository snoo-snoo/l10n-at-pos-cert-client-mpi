# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import logging
import json
from odoo import fields

_logger = logging.getLogger(__name__)


class PosCertWebhook(http.Controller):
    
    @http.route('/webhook/pos_cert/status_update', type='http', auth='public', methods=['POST'], csrf=False)
    def subscription_status_update(self, **kwargs):
        """Handle subscription status updates from admin module"""
        try:
            _logger.info('Received subscription status update webhook')
            
            # Parse the request body
            request_body = request.httprequest.get_data().decode('utf-8')
            _logger.info('Subscription webhook request body: %s', request_body)
            
            try:
                webhook_data = json.loads(request_body)
            except json.JSONDecodeError as e:
                _logger.error('Invalid JSON in subscription webhook: %s', str(e))
                return json.dumps({'success': False, 'error': 'Invalid JSON format'})
            
            # Extract event type and data
            event_type = webhook_data.get('event_type')
            data = webhook_data.get('data', {})
            
            _logger.info('Processing subscription webhook event: %s with data: %s', event_type, data)
            
            if event_type == 'subscription_payment_received':
                # Handle subscription payment received event
                try:
                    _logger.info('Handling subscription payment received event')
                    
                    subscription_id = data.get('subscription_id')
                    payment_status = data.get('payment_status')
                    
                    if not subscription_id:
                        _logger.error('Missing subscription_id in webhook data')
                        return json.dumps({'success': False, 'error': 'Missing subscription_id'})
                    
                    # Handle regular subscription payment - update company status
                    _logger.info('Subscription payment received: ID=%s, Status=%s', subscription_id, payment_status)
                    
                    # Get company by client_company_id from webhook data
                    client_company_id = webhook_data.get('client_company_id')
                    company = request.env['res.company'].sudo().browse(client_company_id) if client_company_id else None
                    
                    if company and company.exists():
                        if payment_status == 'paid':
                            company.write({
                                'pos_cert_status': 'active',
                            })
                            _logger.info('Updated company %s (ID: %s) subscription status to active', company.name, company.id)
                        elif payment_status == 'not_paid':
                            company.write({
                                'pos_cert_status': 'inactive',
                            })
                            _logger.info('Updated company %s (ID: %s) subscription status to inactive', company.name, company.id)
                        else:
                            _logger.info('Payment status %s - no action taken for company %s (ID: %s)', payment_status, company.name, company.id)
                    else:
                        _logger.warning('Company with client_company_id %s not found', client_company_id)
                    
                    return json.dumps({'success': True})
                    
                except Exception as e:
                    _logger.error('Error handling subscription payment received: %s', str(e))
                    return json.dumps({'success': False, 'error': str(e)})
            else:
                _logger.warning('Unknown subscription webhook event type: %s', event_type)
                return json.dumps({'success': False, 'error': 'Unknown event type'})
                
        except Exception as e:
            _logger.error('Error processing subscription webhook: %s', str(e))
            return json.dumps({'success': False, 'error': str(e)})
    
    @http.route('/webhook/pos_cert/cash_register_payment', type='http', auth='public', methods=['POST'], csrf=False)
    def cash_register_payment_update(self, **kwargs):
        """Handle cash register payment updates from admin module"""
        try:
            _logger.info('Received cash register payment update webhook')
            
            # Parse the request body
            request_body = request.httprequest.get_data().decode('utf-8')
            _logger.info('Cash register webhook request body: %s', request_body)
            
            try:
                webhook_data = json.loads(request_body)
            except json.JSONDecodeError as e:
                _logger.error('Invalid JSON in cash register webhook: %s', str(e))
                return json.dumps({'success': False, 'error': 'Invalid JSON format'})
            
            # Extract event type and data
            event_type = webhook_data.get('event_type')
            data = webhook_data.get('data', {})
            
            _logger.info('Processing cash register webhook event: %s with data: %s', event_type, data)
            
            if event_type == 'cash_register_subscription_created':
                # Handle cash register subscription created event
                try:
                    _logger.info('Handling cash register subscription created event')
                    
                    pos_config_id = data.get('pos_config_id')
                    subscription_id = data.get('subscription_id')
                    
                    if not pos_config_id:
                        _logger.error('Missing pos_config_id in webhook data')
                        return json.dumps({'success': False, 'error': 'Missing pos_config_id'})
                    
                    # Find the POS config and update it
                    pos_config = request.env['pos.config'].sudo().browse(pos_config_id)
                    if not pos_config.exists():
                        _logger.error('POS config not found: %s', pos_config_id)
                        return json.dumps({'success': False, 'error': 'POS config not found'})
                    
                    # Update POS config with registration information
                    pos_config.write({
                        'pos_cert_subscription_id': subscription_id,  # Store subscription ID for tracking
                        'pos_cert_status': 'pending',  # Will be updated to 'active' when payment is received
                        'pos_cert_registration_date': fields.Datetime.now(),
                    })
                    
                    _logger.info('Updated POS config %s status to pending', pos_config.name)
                    
                    return json.dumps({'success': True})
                    
                except Exception as e:
                    _logger.error('Error handling cash register subscription created: %s', str(e))
                    return json.dumps({'success': False, 'error': str(e)})
                    
            elif event_type == 'cash_register_payment_received':
                # Handle cash register payment received event
                try:
                    _logger.info('Handling cash register payment received event')
                    
                    pos_config_id = data.get('pos_config_id')
                    payment_status = data.get('payment_status')
                    
                    if not pos_config_id:
                        _logger.error('Missing pos_config_id in cash register webhook data')
                        return json.dumps({'success': False, 'error': 'Missing pos_config_id'})
                    
                    # Find the POS config and update its status
                    pos_config = request.env['pos.config'].sudo().browse(pos_config_id)
                    if not pos_config.exists():
                        _logger.warning('POS config not found: %s', pos_config_id)
                        return json.dumps({'success': True, 'message': 'POS config not found'})
                    
                    # Update POS config status based on payment
                    if payment_status == 'paid':
                        pos_config.write({
                            'pos_cert_status': 'active',
                        })
                        _logger.info('Updated POS config %s status to active', pos_config.name)
                    else:
                        pos_config.write({
                            'pos_cert_status': 'inactive',
                        })
                        _logger.info('Updated POS config %s status to inactive', pos_config.name)
                    
                    return json.dumps({'success': True})
                    
                except Exception as e:
                    _logger.error('Error handling cash register payment received: %s', str(e))
                    return json.dumps({'success': False, 'error': str(e)})
            else:
                _logger.warning('Unknown cash register webhook event type: %s', event_type)
                return json.dumps({'success': False, 'error': 'Unknown event type'})
                
        except Exception as e:
            _logger.error('Error processing cash register webhook: %s', str(e))
            return json.dumps({'success': False, 'error': str(e)}) 