# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import json
from datetime import datetime

_logger = logging.getLogger(__name__)


class PosReceipt(models.Model):
    _name = 'pos.receipt'
    _description = 'POS Receipt for RKSV Compliance'
    _order = 'created_at desc'
    
    # Basic fields
    name = fields.Char(string='Receipt Reference', required=True, copy=False, readonly=True, 
                      default=lambda self: _('New'))
    pos_order_id = fields.Many2one('pos.order', string='POS Order', required=True, ondelete='cascade')
    
    # Receipt data fields (populated from Fiskaly response)
    receipt_id = fields.Char(string='Receipt ID (UUID)', readonly=True)
    receipt_number = fields.Char(string='RKSV Receipt Number', readonly=True)
    time_signature = fields.Integer(string='Time Signature', readonly=True)
    cash_register_serial = fields.Char(string='Cash Register Serial', readonly=True)
    qr_code_data = fields.Text(string='QR Code Data', readonly=True)
    signature_unit_id = fields.Char(string='Signature Unit ID', readonly=True)
    
    # Schema data for retry attempts
    schema_data = fields.Text(string='Receipt Schema', readonly=True)
    
    # Complete Fiskaly response storage
    fiskaly_response = fields.Text(string='Complete Fiskaly Response', readonly=True)
    
    # New fields for offline handling
    is_offline_receipt = fields.Boolean(
        string='Offline Receipt', 
        default=False, 
        help='Indicates if this receipt was generated offline due to API failure'
    )
    request_payload = fields.Text(
        string='Request Payload', 
        readonly=True,
        help='Complete request payload for replay when API comes back online'
    )
    retry_count = fields.Integer(
        string='Retry Count',
        default=0,
        help='Number of times this receipt has been retried'
    )
    last_retry_at = fields.Datetime(
        string='Last Retry At',
        readonly=True
    )
    
    # Status and tracking
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('signed', 'Signed'),
        ('failed', 'Failed')
    ], string='Status', default='draft', required=True)
    error_message = fields.Text(string='Error Message', readonly=True)
    created_at = fields.Datetime(string='Created At', default=fields.Datetime.now, readonly=True)
    signed_at = fields.Datetime(string='Signed At', readonly=True)
    
    # Computed fields
    formatted_time_signature = fields.Char(string='Formatted Time Signature', 
                                         compute='_compute_formatted_time_signature', store=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create method to handle batch creation properly"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('pos.receipt')
        return super().create(vals_list)
    
    @api.depends('time_signature')
    def _compute_formatted_time_signature(self):
        for record in self:
            if record.time_signature:
                try:
                    dt = datetime.fromtimestamp(record.time_signature)
                    record.formatted_time_signature = dt.strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, OSError):
                    record.formatted_time_signature = 'Invalid timestamp'
            else:
                record.formatted_time_signature = ''
    
    def action_retry_fiscalization(self):
        """Retry fiscalization for failed receipts"""
        self.ensure_one()
        
        if not self.schema_data:
            raise ValidationError(_('No schema data available for retry'))
        
        try:
            # Parse stored schema
            schema = json.loads(self.schema_data)
            
            # Prepare retry request
            retry_data = {
                'cash_register_id': self.pos_order_id.config_id.pos_cert_cash_register_id,
                'receipt_id': self.receipt_id,
                'pos_order_id': self.pos_order_id.id,
                'client_company_id': self.pos_order_id.company_id.id,
                'schema': schema
            }
            
            # Call the fiscalization API again
            result = self.pos_order_id.config_id._call_admin_sign_receipt_api(retry_data)
            
            if result.get('success'):
                # Update receipt with successful data
                fiskaly_data = result.get('data', {})
                self.write({
                    'state': 'signed',
                    'signed_at': fields.Datetime.now(),
                    'receipt_number': fiskaly_data.get('receipt_number'),
                    'time_signature': fiskaly_data.get('time_signature'),
                    'cash_register_serial': fiskaly_data.get('cash_register_serial_number'),
                    'qr_code_data': fiskaly_data.get('qr_code_data'),
                    'is_offline_receipt': False,
                    'retry_count': self.retry_count + 1,
                    'last_retry_at': fields.Datetime.now(),
                })
                return True
            else:
                # Update retry count and error
                self.write({
                    'retry_count': self.retry_count + 1,
                    'last_retry_at': fields.Datetime.now(),
                    'error_message': result.get('error', 'Retry failed'),
                })
                return False
                
        except Exception as e:
            _logger.error('Failed to retry fiscalization for receipt %s: %s', self.name, str(e))
            self.write({
                'retry_count': self.retry_count + 1,
                'last_retry_at': fields.Datetime.now(),
                'error_message': f'Retry failed: {str(e)}',
            })
            return False
    
    @api.model
    def _retry_offline_receipts_cron(self):
        """Cron job method to automatically retry offline receipts"""
        try:
            # Find all offline receipts that can be retried
            offline_receipts = self.search([
                ('is_offline_receipt', '=', True),
                ('state', '=', 'failed'),
                ('schema_data', '!=', False),
                ('retry_count', '<', 5)  # Limit retries to prevent infinite loops
            ])
            
            if not offline_receipts:
                _logger.info('No offline receipts to retry')
                return
            
            _logger.info('Found %d offline receipts to retry', len(offline_receipts))
            
            success_count = 0
            for receipt in offline_receipts:
                try:
                    if receipt.action_retry_fiscalization():
                        success_count += 1
                        _logger.info('Successfully retried receipt %s', receipt.name)
                    else:
                        _logger.warning('Failed to retry receipt %s (attempt %d)', receipt.name, receipt.retry_count)
                except Exception as e:
                    _logger.error('Exception while retrying receipt %s: %s', receipt.name, str(e))
                    # Update retry count even on exception
                    receipt.write({
                        'retry_count': receipt.retry_count + 1,
                        'last_retry_at': fields.Datetime.now(),
                        'error_message': f'Cron retry failed: {str(e)}',
                    })
            
            _logger.info('Cron job completed: %d receipts retried successfully out of %d', success_count, len(offline_receipts))
            
        except Exception as e:
            _logger.error('Exception in offline receipts retry cron: %s', str(e))
    
    def action_view_pos_order(self):
        """View the associated POS order"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Order',
            'res_model': 'pos.order',
            'res_id': self.pos_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        } 