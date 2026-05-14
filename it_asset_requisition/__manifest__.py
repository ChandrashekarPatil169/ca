
{
    "name": "IT Asset Requisition",
    "version": "1.1",
    "category": "Purchase",
    "summary": "Website IT Asset Requisition with RFQ Creation",
    "depends": ["base", "purchase", "website", "product", "hr", "approvals", "stock", "project"],
    "data": [
        "security/it_asset_security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/it_asset_views.xml",
        "views/website_form.xml",
        "views/purchase_order_views.xml",
        "views/it_asset_requisition_inherit_views.xml",
        "views/user_access_form_views.xml",
        "report/user_access_form_report.xml"
    ],
    "post_init_hook": "post_init_hook",
    "application": True,
}
