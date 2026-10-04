{
    'name': 'SMSA Express Shipping Connector',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Delivery',
    'summary': 'Integrate Odoo with SMSA Express Shipping API',
    'author': 'iLines Solutions',
    'website': 'https://www.ilines.solutions',
    'depends': ['delivery', 'stock', 'stock_delivery', 'sale_management', 'contacts', 'website_sale', 'base_geolocalize'],
    'data': [
        'security/ir.model.access.csv',
        'data/delivery_smsa_data.xml',
        'views/delivery_carrier_views.xml',
        'views/picking.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
