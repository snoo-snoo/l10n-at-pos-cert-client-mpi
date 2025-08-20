# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import json
import uuid

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'
    
    receipt_id = fields.Many2one('pos.receipt', string='Receipt', compute='_compute_receipt_status', store=True)
    
    # New computed RKSV fields for receipt template
    rksv_cash_register_serial = fields.Char(
        string='RKSV Cash Register Serial',
        compute='_compute_rksv_receipt_data',
        store=False
    )
    rksv_formatted_time = fields.Char(
        string='RKSV Formatted Time',
        compute='_compute_rksv_receipt_data',
        store=False
    )
    rksv_qr_code_data = fields.Text(
        string='RKSV QR Code Data',
        compute='_compute_rksv_receipt_data',
        store=False
    )
    rksv_signing_success = fields.Boolean(
        string='RKSV Signing Success',
        compute='_compute_rksv_receipt_data',
        store=False
    )
    rksv_receipt_number = fields.Char(
        string='RKSV Receipt Number',
        compute='_compute_rksv_receipt_data',
        store=False
    )
    rksv_error_message = fields.Text(
        string='RKSV Error Message',
        compute='_compute_rksv_receipt_data',
        store=False
    )
    rksv_is_offline = fields.Boolean(
        string='RKSV Offline Receipt',
        compute='_compute_rksv_receipt_data',
        store=False
    )
    
    @api.depends('receipt_id.state', 'receipt_id.cash_register_serial', 'receipt_id.time_signature', 
                 'receipt_id.qr_code_data', 'receipt_id.receipt_number', 'receipt_id.error_message',
                 'receipt_id.is_offline_receipt')
    def _compute_rksv_receipt_data(self):
        """Compute RKSV data from associated pos.receipt"""
        for order in self:
            receipt = order.receipt_id
            if receipt:
                order.rksv_cash_register_serial = receipt.cash_register_serial or ''
                order.rksv_formatted_time = receipt.formatted_time_signature or ''
                order.rksv_qr_code_data = receipt.qr_code_data or ''
                order.rksv_signing_success = receipt.state == 'signed'
                order.rksv_receipt_number = receipt.receipt_number or ''
                order.rksv_error_message = receipt.error_message or ''
                order.rksv_is_offline = receipt.is_offline_receipt
            else:
                # Set default values when no receipt exists
                order.rksv_cash_register_serial = ''
                order.rksv_formatted_time = ''
                order.rksv_qr_code_data = ''
                order.rksv_signing_success = False
                order.rksv_receipt_number = ''
                order.rksv_error_message = ''
                order.rksv_is_offline = False
    
    @api.depends('config_id.pos_cert_cash_register_id')
    def _compute_receipt_status(self):
        for order in self:
            if not order.config_id.pos_cert_cash_register_id:
                order.receipt_id = False
            else:
                # Find the receipt for this order
                receipt = self.env['pos.receipt'].search([('pos_order_id', '=', order.id)], limit=1)
                if receipt:
                    order.receipt_id = receipt.id
                else:
                    order.receipt_id = False
    
    def _sign_receipt(self):
        """Sign receipt via admin module with simplified offline handling"""
        self.ensure_one()
        
        try:
            _logger.info('Signing receipt for POS order: %s (ID: %s)', self.name, self.id)
            
            # Check if cash register is configured
            if not self.config_id.pos_cert_cash_register_id:
                _logger.warning('No cash register configured for POS config: %s', self.config_id.name)
                return False
            
            # Generate unique receipt ID
            receipt_id = str(uuid.uuid4())
            _logger.info('Generated receipt ID: %s', receipt_id)
            
            # Prepare receipt data in EKabs schema format
            schema_data = self._prepare_ekabs_schema()
            
            # Prepare receipt request data
            receipt_data = {
                'cash_register_id': self.config_id.pos_cert_cash_register_id,
                'receipt_id': receipt_id,
                'pos_order_id': self.id,
                'client_company_id': self.company_id.id,
                'schema': schema_data
            }
            
            _logger.info('Receipt request data: %s', receipt_data)
            
            # Store complete request payload for potential replay
            request_payload = json.dumps(receipt_data, default=str)
            
            # Call admin module to sign receipt
            result = self.config_id._call_admin_sign_receipt_api(receipt_data)
            
            if result.get('success'):
                # Extract data from response
                response_data = result.get('data', {})
                
                # Create receipt record with complete response data
                receipt_vals = {
                    'pos_order_id': self.id,
                    'receipt_id': receipt_id,
                    'receipt_number': response_data.get('receipt_number'),
                    'time_signature': response_data.get('time_signature'),
                    'cash_register_serial': response_data.get('cash_register_serial_number') or self.config_id.pos_cert_cash_register_serial_number,
                    'qr_code_data': response_data.get('qr_code_data'),
                    'signature_unit_id': response_data.get('signature_creation_unit_id'),
                    'response': json.dumps(response_data),
                    'state': 'signed',
                    'signed_at': fields.Datetime.now(),
                    'is_offline_receipt': False,
                    'request_payload': request_payload,
                    'schema_data': json.dumps(schema_data),
                }
                
                receipt = self.env['pos.receipt'].create(receipt_vals)
                _logger.info('Successfully created receipt record: %s (ID: %s)', receipt.name, receipt.id)
                
                return True
            else:
                # Any non-success response = offline/error scenario
                error_msg = result.get('error', 'Unknown error')
                
                # Generate offline receipt according to SIGN AT requirements
                offline_receipt = self._create_offline_receipt(receipt_id, request_payload, error_msg, schema_data)
                _logger.warning('Created offline receipt due to API failure: %s', error_msg)
                return True  # Return True as we successfully handled the offline scenario
                
        except Exception as e:
            _logger.error('Exception during receipt signing: %s', str(e))
            return False
    
    def _create_offline_receipt(self, receipt_id, request_payload, error_msg, schema_data):
        """Create offline receipt according to SIGN AT requirements"""
        # Generate offline receipt number
        offline_number = self._generate_offline_receipt_number()
        
        # Generate offline QR code data first
        offline_qr_data = self._generate_offline_qr_data(receipt_id)
        
        # Create offline receipt record
        receipt_vals = {
            'pos_order_id': self.id,
            'receipt_id': receipt_id,
            'receipt_number': offline_number,
            'state': 'failed',
            'error_message': error_msg,
            'request_payload': request_payload,
            'is_offline_receipt': True,
            'qr_code_data': offline_qr_data,  # Set QR code data directly
            'schema_data': json.dumps(schema_data),
        }
        
        receipt = self.env['pos.receipt'].create(receipt_vals)
        
        return receipt
    
    def _generate_offline_qr_data(self, receipt_id):
        """Generate QR code data for offline receipts with required SIGN AT data"""
        # Get cash register serial from config
        cash_register_serial = self.config_id.pos_cert_cash_register_serial_number
        
        offline_data = {
            'type': 'offline_receipt',
            'receipt_id': receipt_id,  # The UUID from pos.receipt
            'cash_register_serial': cash_register_serial,
            'order_id': self.name,
            'timestamp': fields.Datetime.now().isoformat(),
            'status': 'offline',
            'message': 'Sicherheitseinrichtung ausgefallen',
            'total_amount': self.amount_total,
            'tax_amount': self.amount_tax
        }
        return json.dumps(offline_data)

    def _generate_offline_receipt_number(self):
        """Generate a temporary receipt number for offline receipts"""
        sequence = self.env['ir.sequence'].next_by_code('pos.receipt.offline')
        return f"OFFLINE-{sequence}"

    def _prepare_ekabs_schema(self):
        """Prepare receipt data in EKabs schema format"""
        self.ensure_one()
        
        # Prepare payment types
        payment_types = []
        for payment in self.payment_ids:
            payment_type = 'CASH' if payment.payment_method_id.is_cash_count else 'NON_CASH'
            payment_types.append({
                'name': payment_type,
                'amount': payment.amount
            })
        
        # Prepare VAT amounts
        vat_amounts = []
        for line in self.lines:
            if line.tax_ids:
                for tax in line.tax_ids:
                    vat_amounts.append({
                        'percentage': tax.amount,
                        'incl_vat': line.price_subtotal_incl,
                        'excl_vat': line.price_subtotal,
                        'vat': line.price_subtotal_incl - line.price_subtotal
                    })
        
        # Prepare line items
        lines = []
        for line in self.lines:
            line_data = {
                'text': line.product_id.name,
                'item': {
                    'number': line.product_id.default_code or '',
                    'quantity': line.qty,
                    'price_per_unit': line.price_unit
                }
            }
            lines.append(line_data)
        
        # Build complete schema
        schema = {
            'ekabs_v0': {
                'head': {
                    'id': str(uuid.uuid4()),  # Required: Unique id of the receipt
                    'number': self.name,       # Required: Receipt number
                    'date': self.date_order.strftime('%Y-%m-%dT%H:%M:%SZ'),  # Required: Receipt date in ISO format with Z timezone
                    'seller': {                # Optional but useful
                        'name': self.company_id.name,
                        'tax_number': self.company_id.vat or '',
                        'address': {
                            'street': self.company_id.street or '',
                            'postal_code': self.company_id.zip or '',
                            'city': self.company_id.city or '',
                            'country_code': self.company_id.country_id.code or 'AT'
                        }
                    }
                },
                'data': {
                    'currency': self.currency_id.name,  # Required: ISO 4217 currency code
                    'full_amount_incl_vat': f"{self.amount_total:.2f}",  # Required: Format as "0.00"
                    'payment_types': payment_types,  # Required: Array of payment objects
                    'vat_amounts': [
                        {
                            'vat_rate': 'STANDARD',  # Required: Enum value
                            'percentage': float(vat.get('percentage')),  # Required: Number with <=2 decimal places
                            'incl_vat': f"{vat.get('incl_vat', 0):.2f}",  # Required: Format as "0.00"
                            'excl_vat': f"{vat.get('excl_vat', 0):.2f}",  # Required: Format as "0.00"
                            'vat': f"{vat.get('vat', 0):.2f}"  # Required: Format as "0.00"
                        }
                        for vat in vat_amounts
                    ],
                    'lines': [
                        {
                            'text': line.get('text', ''),  # Required: Text of the receipt line
                            'item': line.get('item', {})   # Optional: Product item details
                        }
                        for line in lines
                    ]
                }
            }
        }
        
        return schema

    def action_pos_order_paid(self):
        """Override to add receipt signing"""
        res = super().action_pos_order_paid()
        
        # Add receipt signing logic
        if self.config_id.pos_cert_cash_register_id:
            self._sign_receipt()
        
        return res 