/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    /**
     * Extend the export_for_printing method to include RKSV compliance data
     * This data will be available in the receipt template as props.data.rksv_*
     */
    export_for_printing(baseUrl, headerData) {
        const result = super.export_for_printing(...arguments);
        
        // Add RKSV compliance data to the receipt printing data
        // These fields come from the computed fields we added to the Python pos.order model
        result.rksv_cash_register_serial = this.rksv_cash_register_serial || '';
        result.rksv_formatted_time = this.rksv_formatted_time || '';
        result.rksv_qr_code_data = this.rksv_qr_code_data || '';
        result.rksv_signing_success = this.rksv_signing_success || false;
        result.rksv_receipt_number = this.rksv_receipt_number || '';
        result.rksv_error_message = this.rksv_error_message || '';
        result.rksv_is_offline = this.rksv_is_offline || false;
        
        // Generate QR code SVG if we have QR code data
        if (this.rksv_qr_code_data) {
            try {
                const codeWriter = new window.ZXing.BrowserQRCodeSvgWriter();
                const qr_code_svg = new XMLSerializer().serializeToString(
                    codeWriter.write(this.rksv_qr_code_data, 200, 200)
                );
                result.rksv_qr_code_svg = "data:image/svg+xml;base64," + window.btoa(qr_code_svg);
            } catch (error) {
                console.warn('Failed to generate QR code SVG:', error);
                result.rksv_qr_code_svg = null;
            }
        }
        
        return result;
    },
}); 