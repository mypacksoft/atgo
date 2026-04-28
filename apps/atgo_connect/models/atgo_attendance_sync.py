"""Pull ATGO attendance logs and write hr.attendance."""
from datetime import datetime, timezone
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    requests = None


class AtgoAttendanceLog(models.Model):
    """Local cache of pulled logs (so we can ack and dedupe)."""
    _name = "atgo.attendance.log"
    _description = "ATGO attendance log (raw pull)"
    _order = "punched_at desc"

    atgo_log_id = fields.Integer(required=True, index=True)
    device_pin = fields.Char(required=True, index=True)
    employee_id = fields.Many2one("hr.employee")
    punched_at = fields.Datetime(required=True)
    punch_state = fields.Integer()
    device_code = fields.Char()
    state = fields.Selection([
        ("new", "New"),
        ("processed", "Processed"),
        ("skipped", "Skipped"),
        ("error", "Error"),
    ], default="new", index=True)
    error_message = fields.Text()

    _sql_constraints = [
        ("uniq_atgo_log", "UNIQUE(atgo_log_id)", "ATGO log already imported"),
    ]


class AtgoSyncRunner(models.AbstractModel):
    _name = "atgo.sync.runner"
    _description = "ATGO sync runner"

    @api.model
    def cron_pull_attendance(self):
        """Called by ir.cron every N minutes."""
        if requests is None:
            _logger.warning("ATGO Connect: 'requests' library not installed")
            return

        config = self.env["atgo.config"].search([("is_active", "=", True)], limit=1)
        if not config or not config.enable_attendance_sync:
            return

        url = f"{config.gateway_url.rstrip('/')}/api/odoo/attendance-logs"
        try:
            r = requests.get(
                url,
                headers={"Authorization": f"Bearer {config.api_key}"},
                params={"limit": 500},
                timeout=30,
            )
            if r.status_code != 200:
                config.last_error = f"HTTP {r.status_code}: {r.text[:300]}"
                return
            payload = r.json()
        except Exception as e:
            config.last_error = str(e)[:500]
            return

        Log = self.env["atgo.attendance.log"]
        Attendance = self.env["hr.attendance"]
        Employee = self.env["hr.employee"]

        synced_ids: list[int] = []
        for item in payload.get("logs", []):
            if Log.search_count([("atgo_log_id", "=", item["id"])]) > 0:
                synced_ids.append(item["id"])
                continue

            employee = Employee.search(
                [("barcode", "=", item["device_pin"])], limit=1
            )
            log = Log.create({
                "atgo_log_id":  item["id"],
                "device_pin":   item["device_pin"],
                "employee_id":  employee.id if employee else False,
                "punched_at":   item["punched_at"].replace("T", " ").rstrip("Z"),
                "punch_state":  item.get("punch_state"),
                "device_code":  item.get("device_code"),
            })
            if not employee:
                log.write({"state": "skipped",
                           "error_message": "no employee with this PIN"})
                synced_ids.append(item["id"])
                continue

            try:
                punched = fields.Datetime.from_string(log.punched_at)
                state = item.get("punch_state")
                if state in (0, None):  # check_in or auto-toggle
                    open_att = Attendance.search([
                        ("employee_id", "=", employee.id),
                        ("check_out", "=", False),
                    ], limit=1)
                    if open_att and (state is None):
                        open_att.check_out = punched
                    else:
                        Attendance.create({
                            "employee_id": employee.id,
                            "check_in": punched,
                        })
                elif state == 1:  # check_out
                    open_att = Attendance.search([
                        ("employee_id", "=", employee.id),
                        ("check_out", "=", False),
                    ], limit=1, order="check_in desc")
                    if open_att:
                        open_att.check_out = punched
                    else:
                        Attendance.create({
                            "employee_id": employee.id,
                            "check_in": punched,
                            "check_out": punched,
                        })
                log.state = "processed"
                synced_ids.append(item["id"])
            except Exception as e:
                log.write({"state": "error", "error_message": str(e)[:500]})

        if synced_ids:
            try:
                requests.post(
                    f"{config.gateway_url.rstrip('/')}/api/odoo/attendance-logs/ack",
                    headers={"Authorization": f"Bearer {config.api_key}"},
                    json={"log_ids": synced_ids},
                    timeout=15,
                )
            except Exception as e:
                _logger.warning("ATGO Connect: ack failed: %s", e)

        config.last_synced_at = fields.Datetime.now()
        config.last_error = False
