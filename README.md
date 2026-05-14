# CA — Custom Addons

A collection of Odoo 19 custom modules for dealer management, CRM enhancements, procurement workflows, vendor registration, IT asset requisition, and product approval.

## Modules

| Module | Version | Category | Description |
|--------|---------|----------|-------------|
| `dealer_tracking` | 1.0 | Sales / Helpdesk | Track dealer, customer, and location from serial numbers |
| `dgz_crm_orderlines` | 19.0.1 | CRM | Generate sales order lines directly from CRM leads |
| `product_requisition` | 19.0.1.2.0 | Website / CRM | Collect product requisitions from the website and create CRM leads |
| `vendor_registration` | 19.0.1.1.0 | Website / Purchase | Website portal for vendor registration with approval workflow |
| `it_asset_requisition` | 1.1 | Purchase | Website IT Asset Requisition with RFQ creation |
| `zb_product_approve` | 19.0.1.0 | Inventory | Product approval workflow with Draft and Approve stages |

## Module Details

### Dealer Tracking with Serial Link
Track dealers, customers, and locations through product serial numbers with helpdesk ticket integration.

### CRM Order Lines (`dgz_crm_orderlines`)
Adds the ability to define default order lines on CRM leads. When a quotation is created from CRM, it is pre-loaded with those order lines.

### Website Product Requisition
Provides a website form for customers to submit product requisition requests. Submissions create CRM leads with order lines for follow-up.

### Vendor Registration Portal
Full vendor registration workflow including:
- Public website registration form
- Admin approval process
- Vendor product/service submission portal
- Mail notifications at each stage

### IT Asset Requisition
Website-based IT asset request form that generates purchase RFQs. Includes user access forms and approval workflows.

### Product Approval (`zb_product_approve`)
Adds Draft → Approved lifecycle to products. Sales and Purchase orders can only use approved products.

## Installation

1. Copy the desired module(s) into your Odoo addons directory.
2. Update the module list: **Settings → Technical → Update Apps List**.
3. Search for the module name and click **Install**.

> **Note:** Some modules have inter-dependencies (e.g., `product_requisition` depends on `dgz_crm_orderlines` and `zb_product_approve`). Install dependencies first.

## Requirements

- Odoo 19.0 (Community or Enterprise)
- Python 3.10+

## License

LGPL-3 — see individual module manifests for details.
