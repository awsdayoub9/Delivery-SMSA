import requests
import json
import logging
import base64
from odoo import models, fields, _
from odoo.exceptions import UserError
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(
        selection_add=[('smsa', 'SMSA Express')],
        ondelete={'smsa': 'set default'}
    )

    smsa_api_url_live = fields.Char(
        string='SMSA API URL (Live)',
        default='https://ecom.smsaexpress.com',
        help="The base URL for the SMSA E-Commerce Live API, e.g., 'https://ecom.smsaexpress.com'"
    )
    smsa_api_url_test = fields.Char(
        string='SMSA API URL (Test)',
        default='https://ecomapis-sandbox.azurewebsites.net',
        help="The base URL for the SMSA E-Commerce Test API, e.g., 'https://ecomapis-sandbox.azurewebsites.net'"
    )
    smsa_apikey_live = fields.Char(string='SMSA Live API Key (apikey)')
    smsa_apikey_test = fields.Char(string='SMSA Test API Key (apikey)')

    smsa_shipper_contact = fields.Char(string='Shipper Contact Name', required=True)
    smsa_shipper_phone = fields.Char(string='Shipper Phone', required=True)
    smsa_shipper_city = fields.Char(string='Shipper City', required=True, help="e.g., 'Riyadh'")
    smsa_shipper_country = fields.Char(string='Shipper Country Code', required=True, default='SA')
    smsa_shipper_address_line1 = fields.Char(string='Shipper Address Line 1', required=True)
    smsa_shipper_postal_code = fields.Char(string='Shipper Postal Code')
    smsa_shipper_district = fields.Char(string='Shipper District')

    smsa_service_code = fields.Char(
        string='Default Service Code',
        default='EDDL',
        help="The default service code, e.g., 'EDDL' (ECOM Delivery lite). Found via 'Get Service Types Lookup' API."
    )
    smsa_waybill_type = fields.Selection(
        [('PDF', 'PDF'), ('ZPL', 'ZPL')],
        string='Label Format (Waybill Type)',
        default='PDF'
    )


    def _smsa_get_headers(self, host_name):
        """ Returns the required headers for SMSA API requests. """
        self.ensure_one()
        if ((not self.smsa_apikey_live and self.prod_environment) or (not self.smsa_apikey_test and not self.prod_environment)):
            raise UserError(_("SMSA 'API Key' is not set in the shipping method configuration."))

        print("GET HEADERS")
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'ApiKey': self.smsa_apikey_live if self.prod_environment else self.smsa_apikey_test,
            'Host': host_name
        }

    def _smsa_make_request(self, endpoint, method='POST', payload=None):
        """ Generic function to make requests to the SMSA API. """
        self.ensure_one()
        if ((not self.smsa_apikey_live and self.prod_environment) or (not self.smsa_apikey_test and not self.prod_environment)):
            raise UserError(_("SMSA API URL is not set."))
        if self.prod_environment:
            url = self.smsa_api_url_live.rstrip('/') + endpoint
        else:
            url = self.smsa_api_url_test.rstrip('/') + endpoint
        host_name = urlparse(url).netloc
        headers = self._smsa_get_headers(host_name)
        print("url",url)
        print("headers",headers)

        log_payload = payload.copy() if payload else {}
        if 'passkey' in log_payload:
            log_payload['passkey'] = '********'

        _logger.info(f"SMSA Request: {method} {url}\nPayload: {json.dumps(log_payload)}")

        try:
            if method.upper() == 'POST':
                response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
            elif method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=payload, timeout=15)
            else:
                raise UserError(_(f"Unsupported HTTP method: {method}"))

            response.raise_for_status()

            if response.status_code == 200 and not response.text:
                _logger.info("SMSA Response: 200 OK (Empty Body)")
                return {'status': 'success', 'message': 'Operation successful (empty response)'}

            res_json = response.json()
            _logger.info(f"SMSA Response: {json.dumps(res_json)}")

            if isinstance(res_json, dict) and res_json.get('status') == 'Failed':
                error_msg = res_json.get('message', 'Unknown error from SMSA API.')
                raise UserError(_(f"SMSA API Error: {error_msg}"))

            return res_json

        except requests.exceptions.HTTPError as e:
            try:
                error_json = e.response.json()
                _logger.error(f"SMSA HTTP Error: {json.dumps(error_json)}")
                error_title = error_json.get('title', 'Unknown Error')
                error_details = "\n".join(
                    [f"- {k}: {v[0]}" for k, v in error_json.get('errors', {}).items()]
                )
                raise UserError(_(f"SMSA API Error (400):\n{error_title}\n{error_details}"))
            except json.JSONDecodeError:
                _logger.error(f"SMSA HTTP Error: {e.response.text}")
                raise UserError(_(f"SMSA API Error: {e.response.status_code}\n{e.response.text}"))
        except requests.exceptions.RequestException as e:
            _logger.error(f"SMSA Connection Error: {e}")
            raise UserError(_(f"Could not connect to SMSA API: {e}"))
        except json.JSONDecodeError:
            _logger.error(f"SMSA Error: Failed to decode JSON response: {response.text}")
            raise UserError(_(f"SMSA returned an invalid response:\n{response.text}"))


    def smsa_get_tracking_link(self, picking):
        """
        Odoo calls this to get the tracking link for the "Tracking" button.
        This provides a public URL for tracking.
        """
        return f'https://smsaexpress.com/trackingdetails?tracknumbers={picking.carrier_tracking_ref}'

    def smsa_rate_shipment(self, order):
        """
        Odoo calls this on the website checkout page.
        Since SMSA has no "Get Rate" API, this function uses Odoo's
        internal "Pricing" tab rules to calculate the cost.
        """

        carrier = self._match_address(order.partner_shipping_id)
        if not carrier:
            return {
                'success': False,
                'price': 0.0,
                'error_message': _('Error: this delivery method is not available for this address.'),
                'warning_message': False
            }

        try:
            price_unit = self._get_price_available(order)
        except UserError as e:
            return {
                'success': False,
                'price': 0.0,
                'error_message': e.args[0],
                'warning_message': False
            }

        if order.company_id.currency_id.id != order.pricelist_id.currency_id.id:
            price_unit = self.env['res.currency']._compute(
                order.company_id.currency_id,
                order.pricelist_id.currency_id,
                price_unit
            )

        return {
            'success': True,
            'price': price_unit,
            'error_message': False,
            'warning_message': False
        }

    def smsa_send_shipping(self, pickings):
        """
        Odoo calls this when validating a Delivery Order.
        This creates the shipment, gets the tracking number, AND gets the label.
        """
        self.ensure_one()
        results = []

        for picking in pickings:
            try:
                payload = self._smsa_prepare_b2c_shipment_payload(picking)
            except Exception as e:
                _logger.error(f"Failed to prepare SMSA payload: {e}")
                results.append({
                    'success': False,
                    'error_message': str(e),
                    'tracking_number': False,
                    'exact_price': 0.0
                })
                continue

            try:
                response = self._smsa_make_request('/api/shipment/b2c/new', method='POST', payload=payload)
            except Exception as e:
                results.append({
                    'success': False,
                    'error_message': str(e),
                    'tracking_number': False,
                    'exact_price': 0.0
                })
                continue

            if not response.get('waybills') or not isinstance(response['waybills'], list) or not response['waybills'][
                0]:
                msg = response.get('message', 'Invalid response structure from SMSA. "waybills" array not found.')
                results.append({
                    'success': False,
                    'error_message': msg,
                    'tracking_number': False,
                    'exact_price': 0.0
                })
                continue

            waybill_data = response['waybills'][0]
            tracking_number = waybill_data.get('awb')
            label_base64 = waybill_data.get('awbFile')

            actual_price = 0.0
            _logger.info(f"SMSA shipment {tracking_number} created. Cost not returned by API, setting to 0.0.")

            if not tracking_number:
                msg = response.get('message', 'Tracking number (awb) not found in SMSA waybills response.')
                results.append({
                    'success': False,
                    'error_message': msg,
                    'tracking_number': False,
                    'exact_price': 0.0
                })
                continue

            if label_base64:
                try:
                    label_data = base64.b64decode(label_base64)
                    picking.message_post(
                        body=_(f'SMSA Shipping Label for {tracking_number}'),
                        attachments=[(f'SMSA-{tracking_number}.pdf', label_data)]
                    )
                except Exception as e:
                    _logger.error(f"Failed to decode or attach SMSA label for {tracking_number}: {e}")
                    picking.message_post(body=_(f"Failed to auto-download SMSA label: {e}"))
            else:
                picking.message_post(body=_(
                    f"SMSA shipment {tracking_number} created, but no label (awbFile) was returned in the API response."))

            results.append({
                'success': True,
                'tracking_number': tracking_number,
                'exact_price': float(actual_price),
                'error_message': False,
            })

        return results

    def smsa_cancel_shipment(self, picking):
        """
        Odoo calls this when a user cancels a picking.
        """
        self.ensure_one()
        tracking_number = picking.carrier_tracking_ref
        if not tracking_number:
            return {'success': True}

        picking.write({
            'carrier_tracking_ref': False,
            'carrier_price': 0.0
        })

        warning_msg = _(
            "The shipment details have been cleared in Odoo. "
            "However, no API endpoint for canceling B2C shipments was found in the documentation. "
            "You MUST log in to your SMSA portal to cancel shipment {tracking_number} to avoid being charged."
        ).format(tracking_number=tracking_number)

        picking.message_post(body=warning_msg)

        return {
            'success': True,
            'error_message': False,
            'warning_message': warning_msg
        }


    def _smsa_get_consignee_address(self, partner):
        """ Helper to build the 'ConsigneeAddress' object. """
        if not partner.city or not partner.phone or not partner.country_id:
            raise UserError(
                _("The customer (recipient) is missing a City, Phone, or Country. These are required by SMSA."))

        if not partner.partner_latitude or not partner.partner_longitude:
            raise UserError(
                _("The customer (recipient) is missing Latitude or Longitude. These are required by SMSA.\n\n"
                  "Please edit the customer's contact record and fill in both 'Latitude' and 'Longitude' fields."))

        coords = f"{partner.partner_latitude},{partner.partner_longitude}"


        return {
            "ContactName": partner.name,
            "ContactPhoneNumber": partner.mobile or partner.phone,
            "Coordinates": coords,
            "Country": partner.country_id.code,
            "District": partner.state_id.name or '',
            "PostalCode": partner.zip or '',
            "City": partner.city,
            "AddressLine1": partner.street or 'N/A',
            "AddressLine2": partner.street2 or '',
            "ConsigneeID": partner.vat or '',
            "ShortCode": ""
        }

    def _smsa_get_shipper_address(self):
        """ Helper to build the 'ShipperAddress' object from config. """
        self.ensure_one()
        return {
            "ContactName": self.smsa_shipper_contact,
            "ContactPhoneNumber": self.smsa_shipper_phone,
            "Coordinates": "",
            "Country": self.smsa_shipper_country,
            "District": self.smsa_shipper_district or '',
            "PostalCode": self.smsa_shipper_postal_code or '',
            "City": self.smsa_shipper_city,
            "AddressLine1": self.smsa_shipper_address_line1,
            "AddressLine2": ""
        }

    def _smsa_prepare_b2c_shipment_payload(self, picking):
        """
        Gathers data from the delivery order and formats it
        for the SMSA /api/shipment/b2c/new API.
        """
        self.ensure_one()
        recipient = picking.partner_id

        total_weight_kg = picking.shipping_weight
        if not total_weight_kg:
            total_weight_kg = sum(move.quantity * move.product_id.weight for move in picking.move_ids)
        if not total_weight_kg or total_weight_kg <= 0:
            total_weight_kg = 1.0


        parcels = len(picking.move_line_ids.mapped('result_package_id')) or 1

        content_desc = ", ".join(
            f"{int(m.quantity)}x {m.product_id.name}" for m in picking.move_ids if m.quantity
        )
        if not content_desc:
            content_desc = picking.origin or "Odoo Shipment"

        cod_amount = 0.0
        if picking.sale_id and picking.sale_id.payment_term_id and 'cash on delivery' in picking.sale_id.payment_term_id.name.lower():
            cod_amount = picking.sale_id.amount_total

        payload = {
            "CODAmount": cod_amount,
            "ConsigneeAddress": self._smsa_get_consignee_address(recipient),
            "ContentDescription": content_desc,
            "DeclaredValue": picking.sale_id.amount_untaxed if picking.sale_id else 0.0,
            "DutyPaid": False,
            "OrderNumber": picking.origin or picking.name,
            "Parcels": parcels,
            "ServiceCode": self.smsa_service_code,
            "ShipDate": fields.Datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            "ShipmentCurrency": picking.sale_id.currency_id.name or "SAR",
            "SMSRetailID": "",
            "ShipperAddress": self._smsa_get_shipper_address(),
            "WaybillType": self.smsa_waybill_type,
            "Weight": total_weight_kg,
            "WeightUnit": "KG",
            "VatPaid": False,
        }

        return payload

