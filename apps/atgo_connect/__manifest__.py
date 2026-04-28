{
    "name": "ATGO Connect — ZKTeco Cloud Attendance",
    "version": "19.0.0.1.0",
    "summary": "Pull ZKTeco attendance from ATGO Cloud into Odoo HR. No static IP, no port forwarding.",
    "description": """
ATGO Connect for Odoo
======================
Connects Odoo HR with ATGO Cloud — a free online attendance platform for
ZKTeco devices. Your devices push punches to ATGO over the internet
(no static IP, no port forwarding, no local server needed); Odoo pulls
them on a 5-minute cron and writes them into ``hr.attendance``.

Features
--------
* Pull attendance logs from ATGO Cloud and create ``hr.attendance``
* Map device PIN to ``hr.employee.barcode``
* Optional employee push from Odoo to ATGO (one-way sync)
* Cron-driven, runs entirely outbound (no inbound port required)
* Compatible with Odoo 16.0, 17.0, 18.0, 19.0

Setup
-----
1. Install this module
2. Go to **ATGO -> Settings**
3. Enter your ATGO workspace slug + API key (generated from your ATGO portal)
4. Click *Test connection*
5. Cron picks up new punches every 5 minutes
""",
    "author": "ATGO",
    "maintainer": "ATGO",
    "website": "https://atgo.io",
    "support": "support@atgo.io",
    "license": "LGPL-3",
    "category": "Human Resources/Attendances",
    "depends": ["base", "hr", "hr_attendance"],
    "external_dependencies": {
        "python": ["requests"],
    },
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/atgo_config_views.xml",
        "views/atgo_device_views.xml",
        "views/hr_employee_views.xml",
        "views/menu.xml",
    ],
    "images": [
        "static/description/banner.png",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
