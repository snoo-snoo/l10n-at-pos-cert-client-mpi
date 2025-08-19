# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
import requests
import json
from datetime import datetime

_logger = logging.getLogger(__name__)


class PosCertDep7ExportWizard(models.TransientModel):
    _name = 'pos_cert_dep7_export_wizard'
    _description = 'POS Certification DEP7 Export Wizard'
    
    pos_config_id = fields.Many2one('pos.config', string='POS Config', required=True)
    start_receipt_number = fields.Integer(string='Start Receipt Number')
    end_receipt_number = fields.Integer(string='End Receipt Number')
    start_time_signature = fields.Datetime(string='Start Time Signature')
    end_time_signature = fields.Datetime(string='End Time Signature')
    
    def _convert_datetime_to_timestamp(self, dt):
        """Convert Odoo datetime to Unix timestamp"""
        if dt:
            return int(dt.timestamp())
        return None
    
    def _call_admin_export_api(self):
        """Call the admin module's export DEP7 endpoint"""
        try:
            company = self.pos_config_id.company_id
            
            # Prepare export data
            export_data = {
                'cash_register_id': self.pos_config_id.pos_cert_cash_register_id,
                'start_receipt_number': self.start_receipt_number,
                'end_receipt_number': self.end_receipt_number,
                'start_time_signature': self._convert_datetime_to_timestamp(self.start_time_signature),
                'end_time_signature': self._convert_datetime_to_timestamp(self.end_time_signature),
            }
            
            # Remove None values
            export_data = {k: v for k, v in export_data.items() if v is not None}
            
            # Make API call to admin module
            api_url = f"{company.pos_cert_admin_url}/api/pos_cert/export_dep7"
            headers = {
                'Authorization': f'Bearer {company.pos_cert_api_key}',
                'Content-Type': 'application/json'
            }
            
            _logger.info('Calling admin export DEP7 API: %s', api_url)
            _logger.info('Export data: %s', export_data)
            
            response = requests.post(
                api_url, 
                json=export_data, 
                headers=headers, 
                timeout=60
            )
            
            _logger.info('Admin API response status: %s', response.status_code)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    _logger.info('Successfully exported DEP7 data')
                    return data
                else:
                    _logger.error('Failed to export DEP7 data: %s', data.get('error'))
                    return {'success': False, 'error': data.get('error')}
            else:
                _logger.error('HTTP error %s: %s', response.status_code, response.text)
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            _logger.error('Unexpected error calling admin export DEP7 API: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    def action_export_dep7(self):
        """Export DEP7 data"""
        self.ensure_one()
        
        try:
            # Call admin module to export DEP7 data
            export_result = self._call_admin_export_api()
            
            if not export_result.get('success'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Export Failed',
                        'message': f'Failed to export DEP7 data: {export_result.get("error")}',
                        'type': 'danger',
                    }
                }
            
            # Get the export data and create a temporary file
            export_data = export_result.get('data', {})
            
            # Create a temporary file for download using base64 encoding
            import base64
            # Include cash register serial number in filename if available
            serial_number = self.pos_config_id.pos_cert_cash_register_serial_number or 'unknown'
            filename = f'dep7_export_{serial_number}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            
            file_content = json.dumps(export_data, indent=2)
            file_data = base64.b64encode(file_content.encode('utf-8')).decode('utf-8')
            
            # Create an attachment record for the download with proper MIME type
            attachment = self.env['ir.attachment'].create({
                'name': filename,
                'type': 'binary',
                'datas': file_data,
                'mimetype': 'application/json; charset=utf-8',
                'res_model': self._name,
                'res_id': self.id,
            })
            
            # Return action to download the file with explicit filename
            download_url = f'/web/content/{attachment.id}?download=true&filename={filename}'
            
            return {
                'type': 'ir.actions.act_url',
                'url': download_url,
                'target': 'self',
            }
            
        except Exception as e:
            _logger.error('Error exporting DEP7 data: %s', str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Error exporting DEP7 data: {str(e)}',
                    'type': 'danger',
                }
            } 