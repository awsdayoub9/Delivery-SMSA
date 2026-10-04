import json
import requests
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.fields import Datetime as odoo_datetime


class StockPicking(models.Model):
    _inherit = "stock.picking"

    smsa_scan_ids = fields.One2many(
        "smsa.scan",
        "picking_id",
        string="SMSA Scans"
    )

    smsa_last_status = fields.Char(string="Last SMSA Status")

    def action_get_smsa_scans(self):
        for rec in self:
            awb = rec.carrier_tracking_ref
            if not awb:
                raise UserError(_("No Tracking Number (AWB) found."))

            carrier = rec.carrier_id
            if not carrier or carrier.delivery_type != 'smsa':
                raise UserError(_("Delivery method is not SMSA."))

            url = (carrier.smsa_api_url_live if carrier.prod_environment else carrier.smsa_api_url_test).rstrip(
                '/') + "/api/track/bulk"
            headers = {
                'Content-Type': 'application/json',
                'ApiKey': carrier.smsa_apikey_live if carrier.prod_environment else carrier.smsa_apikey_test
            }

            payload = [awb]

            try:
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                response.raise_for_status()
            except requests.RequestException as e:
                raise UserError(_("SMSA API Error: %s") % e)

            data = response.json()
            if not isinstance(data, list):
                raise UserError(_("Unexpected SMSA response: %s") % json.dumps(data))

            rec.smsa_scan_ids.unlink()
            latest_status = ""

            for ship in data:
                for s in ship.get("Scans", []):
                    scan_datetime = s.get("ScanDateTime")
                    if scan_datetime:
                        scan_datetime = scan_datetime.split('.')[0]
                        scan_datetime = scan_datetime.replace("T", " ")
                        scan_datetime = odoo_datetime.to_datetime(scan_datetime)

                    self.env['smsa.scan'].create({
                        'picking_id': rec.id,
                        'awb': ship.get("AWB"),
                        'reference_id': s.get("ReferenceID"),
                        'city': s.get("City"),
                        'scan_type': s.get("ScanType"),
                        'scan_description': s.get("ScanDescription"),
                        'scan_datetime': scan_datetime,
                        'scan_timezone': s.get("ScanTimeZone"),
                        'received_by': s.get("ReceivedBy"),
                    })
                    latest_status = s.get("ScanDescription") or latest_status

            rec.smsa_last_status = latest_status or "No scans"

        return True
class StockPickingSmsaScan(models.Model):
    _name = "smsa.scan"
    _description = "SMSA Shipment Scan"

    picking_id = fields.Many2one("stock.picking", string="Picking", ondelete="cascade")
    awb = fields.Char(string="AWB")
    reference_id = fields.Char(string="Reference ID")
    city = fields.Char(string="City")
    scan_type = fields.Char(string="Scan Type")
    scan_description = fields.Char(string="Scan Description")
    scan_datetime = fields.Datetime(string="Scan Date")
    scan_timezone = fields.Char(string="TZ")
    received_by = fields.Char(string="Received By")
