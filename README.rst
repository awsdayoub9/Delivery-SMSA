===============================
SMSA Express Shipping Connector
===============================

Odoo 18 module (``delivery_smsa``) that adds **SMSA Express** as a shipping
provider. It creates SMSA B2C shipments when a delivery order is validated,
attaches the waybill label to the delivery order, and pulls tracking scans
back into Odoo.

* **Version:** 18.0.1.0.0
* **Author:** iLines Solutions
* **License:** LGPL-3

Features
========

* New provider **SMSA Express** on shipping methods, with separate Live and
  Test API URL and API key. The carrier's *Environment* setting
  (Production / Test) decides which pair is used.
* **Shipment creation:** validating a delivery order that uses an SMSA
  shipping method calls ``POST /api/shipment/b2c/new``. The returned AWB is
  saved as the tracking reference.
* **Waybill label:** the label returned by SMSA is posted in the delivery
  order's chatter as ``SMSA-<AWB>.pdf``.
* **Tracking link:** the standard *Tracking* button opens
  ``https://smsaexpress.com/trackingdetails?tracknumbers=<AWB>``.
* **Tracking scans:** a **Get SMSA Scans** button on the delivery order calls
  ``POST /api/track/bulk`` and lists the scan history in an **SMSA Tracking**
  tab, along with the last known status.
* **Cash on delivery:** if the sale order's payment term name contains
  "cash on delivery", the sale order total is sent as the COD amount.
* **Website checkout pricing:** SMSA has no rate API, so prices come from the
  shipping method's **Pricing** rules (the tab is shown for SMSA carriers).

Dependencies
============

Odoo modules: ``delivery``, ``stock``, ``stock_delivery``,
``sale_management``, ``contacts``, ``website_sale``, ``base_geolocalize``.

Python packages: ``requests``.

Installation
============

#. Copy the ``delivery_smsa`` folder into your addons path.
#. Update the apps list and install **SMSA Express Shipping Connector**.

Installation creates a service product **SMSA Express Shipping** (code
``SM``) and a shipping method **SMSA Express** that uses it.

Configuration
=============

Open **Inventory > Configuration > Delivery > Shipping Methods > SMSA
Express**, then:

#. Set the *Environment* to Test or Production.
#. On the **SMSA Configuration** tab, fill in:

   * **API Credentials:** API URL and API key for the selected environment.

     * Live URL default: ``https://ecom.smsaexpress.com``
     * Test URL default: ``https://ecomapis-sandbox.azurewebsites.net``

   * **Default Shipper Details:** contact name, phone, address line 1, city,
     district, postal code, country code (default ``SA``).
   * **Default Service:** service code (default ``EDDL``, ECOM Delivery Lite)
     and label format (PDF or ZPL).

#. On the **Pricing** tab, add the price rules used at checkout and on sale
   orders.

Customer requirements
---------------------

SMSA rejects a shipment unless the recipient contact has:

* City, phone (or mobile) and country
* **Latitude and longitude** (from ``base_geolocalize``)

The contact's state is sent as the district and its VAT number as the
consignee ID.

Usage
=====

#. Confirm a sale order with an SMSA shipping method.
#. Validate the delivery order. The AWB is stored as the tracking reference
   and the label appears in the chatter.
#. Click **Get SMSA Scans** at any time to refresh the scan history on the
   **SMSA Tracking** tab.

What is sent to SMSA
--------------------

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Field
     - Source
   * - Weight (KG)
     - Delivery order shipping weight, otherwise sum of product weights,
       otherwise 1
   * - Parcels
     - Number of destination packages, otherwise 1
   * - Content description
     - ``<qty>x <product>`` for each move, otherwise the source document
   * - Declared value
     - Sale order untaxed amount
   * - Order number
     - Source document, otherwise the delivery order name
   * - Currency
     - Sale order currency, otherwise SAR

Known limitations
=================

* **No cancel API.** Cancelling a shipment only clears the tracking reference
  in Odoo and posts a warning in the chatter. The shipment must also be
  cancelled manually in the SMSA portal to avoid being charged.
* **No shipping cost from SMSA.** The API does not return a cost, so the
  carrier price recorded on the delivery order is 0.
* The label attachment always uses a ``.pdf`` extension, even when the label
  format is ZPL.
* The **Get SMSA Scans** button appears on all transfers; it shows an error
  if the transfer has no AWB or does not use an SMSA carrier.
* The scan list is hidden once the delivery order is done; the last status
  field stays visible.

Technical overview
==================

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - File
     - Purpose
   * - ``models/delivery_carrier.py``
     - Extends ``delivery.carrier``: SMSA fields, API requests,
       rate/send/cancel/tracking hooks
   * - ``models/picking.py``
     - Extends ``stock.picking`` with the scans button and last status;
       defines ``smsa.scan``
   * - ``views/delivery_carrier_views.xml``
     - SMSA Configuration tab on the shipping method form
   * - ``views/picking.xml``
     - Get SMSA Scans button and SMSA Tracking tab on the delivery order
   * - ``data/delivery_smsa_data.xml``
     - Default delivery product and SMSA carrier (``noupdate``)
   * - ``security/ir.model.access.csv``
     - Access rights for ``smsa.scan``

API requests and responses are logged under the ``odoo.addons.delivery_smsa``
logger.
