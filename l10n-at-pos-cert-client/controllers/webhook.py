# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import logging
import json

_logger = logging.getLogger(__name__)


class PosCertWebhook(http.Controller):
    
    @http.route('/api/webhook/pos_cert_status', type='http', auth='public', methods=['POST'], csrf=False)
    def pos_cert_status_webhook(self, **kwargs):
        """Handle POS certification status webhook from admin module"""
        try:
            # Parse the raw JSON request body
            request_body = request.httprequest.get_data().decode('utf-8')
            _logger.info('Received webhook request body: %s', request_body)
            
            # Parse the JSON data
            try:
                webhook_data = json.loads(request_body)
            except json.JSONDecodeError as e:
                _logger.error('Invalid JSON in webhook: %s', str(e))
                return json.dumps({'success': False, 'error': 'Invalid JSON format'})
            
            _logger.info('Parsed webhook data: %s', webhook_data)
            
            # Extract webhook data
            event_type = webhook_data.get('event_type')
            partner_id = webhook_data.get('partner_id')
            subscription_status = webhook_data.get('subscription_status')
            product_id = webhook_data.get('product_id')
            product_name = webhook_data.get('product_name')
            client_company_id = webhook_data.get('client_company_id')
            data = webhook_data.get('data', {})
            
            if not event_type:
                _logger.error('Missing event_type in webhook data')
                return json.dumps({'success': False, 'error': 'Missing event_type'})
            
            # Find the correct company by ID
            if client_company_id:
                company = request.env['res.company'].sudo().browse(client_company_id)
                if not company.exists():
                    _logger.error('Company not found with ID: %s', client_company_id)
                    return json.dumps({'success': False, 'error': f'Company not found with ID: {client_company_id}'})
            else:
                # Fallback to default company if no company ID provided
                company = request.env.company.sudo()
            
            _logger.info('Webhook processing for company ID: %s, Name: %s', company.id, company.name)
            
            # Update company status based on webhook event
            if event_type == 'subscription_created':
                _logger.info('Subscription created for company %s', company.name)
                # Status should already be 'pending' from the wizard, so we don't change it here
                # It will be updated to 'active' when payment is received
                
            elif event_type == 'payment_received':
                _logger.info('Payment received for company %s', company.name)
                _logger.info('Current company status before update: %s', company.pos_cert_status)
                company.write({
                    'pos_cert_status': 'active',
                })
                _logger.info('Company status after update: %s', company.pos_cert_status)
                
            elif event_type == 'payment_partial':
                _logger.info('Partial payment received for company %s', company.name)
                # Keep status as is, just log the event
                
            elif event_type == 'payment_overdue':
                _logger.warning('Payment overdue for company %s', company.name)
                company.write({
                    'pos_cert_status': 'suspended',
                })
                
            else:
                _logger.warning('Unknown event type: %s', event_type)
            
            _logger.info('Successfully processed webhook event %s for company %s', event_type, company.name)
            
            return json.dumps({'success': True})
            
        except Exception as e:
            _logger.error('Error processing POS certification status webhook: %s', str(e))
            return json.dumps({'success': False, 'error': str(e)}) 