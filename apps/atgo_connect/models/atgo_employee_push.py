"""Push hr.employee → ATGO Cloud (one-way upsert).

Triggered manually from a server action, or scheduled by a cron.
Fields synced: employee_code (or barcode), name, work email, active.
We never push biometric templates.
"""
from __future__ import annotations

import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import requests
except ImportError:
    requests = None

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    atgo_synced_at = fields.Datetime(readonly=True)
    atgo_sync_error = fields.Char(readonly=True)

    def action_atgo_push(self):
        """Push selected employees to ATGO."""
        if requests is None:
            raise UserError(_("Python 'requests' library is required"))
        config = self.env["atgo.config"].search([("is_active", "=", True)], limit=1)
        if not config or not config.enable_employee_push:
            raise UserError(_("ATGO push is disabled. Enable it in Settings."))

        url = config.gateway_url.rstrip("/") + "/api/employees"
        ok = 0
        for emp in self:
            pin = emp.barcode or emp.identification_id or str(emp.id)
            payload = {
                "employee_code": str(emp.id),
                "device_pin":    str(pin),
                "full_name":     emp.name or pin,
                "email":         emp.work_email or None,
                "phone":         emp.work_phone or None,
                "is_active":     bool(emp.active),
            }
            try:
                r = requests.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {config.api_key}"},
                    timeout=15,
                )
                # 409 means it's already there — treat as success
                if r.status_code in (200, 201, 409):
                    emp.write({"atgo_synced_at": fields.Datetime.now(),
                                "atgo_sync_error": False})
                    ok += 1
                else:
                    emp.atgo_sync_error = f"HTTP {r.status_code}: {r.text[:200]}"
            except Exception as e:
                emp.atgo_sync_error = str(e)[:200]

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("ATGO push"),
                "message": _("Pushed %d / %d employee(s).") % (ok, len(self)),
                "type": "success" if ok == len(self) else "warning",
            },
        }
