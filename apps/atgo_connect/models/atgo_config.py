"""ATGO Connect — global configuration (singleton)."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

import requests


class AtgoConfig(models.Model):
    _name = "atgo.config"
    _description = "ATGO Connect Configuration"
    _rec_name = "tenant_slug"

    tenant_slug = fields.Char(string="Workspace slug", required=True,
                              help="Your ATGO workspace slug, e.g. 'abcschool'")
    gateway_url = fields.Char(string="API base URL", required=True,
                              default="https://api.atgo.io")
    api_key = fields.Char(string="API key", required=True,
                          help="Generate from ATGO portal → Settings → API keys")
    sync_interval_minutes = fields.Integer(default=5)
    last_synced_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)
    is_active = fields.Boolean(default=True)

    enable_attendance_sync = fields.Boolean(default=True)
    enable_employee_push = fields.Boolean(default=False)

    plan_name = fields.Char(readonly=True)
    device_count = fields.Integer(readonly=True)

    def action_test_connection(self):
        self.ensure_one()
        try:
            r = requests.get(
                f"{self.gateway_url.rstrip('/')}/api/odoo/plan-usage",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            if r.status_code != 200:
                raise UserError(_("Connection failed: %s") % r.text[:300])
            data = r.json()
            self.write({
                "plan_name": data.get("plan_id"),
                "device_count": data.get("device_count", 0),
                "last_error": False,
            })
        except Exception as e:
            raise UserError(_("Connection error: %s") % e)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("ATGO"),
                "message": _("Connected successfully."),
                "type": "success",
            },
        }
