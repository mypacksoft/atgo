"""Read-only mirror of ATGO devices."""
from odoo import fields, models


class AtgoDevice(models.Model):
    _name = "atgo.device"
    _description = "ATGO Device (mirror)"

    name = fields.Char(required=True)
    serial_number = fields.Char(readonly=True)
    device_code = fields.Char(readonly=True)
    model = fields.Char(readonly=True)
    firmware_version = fields.Char(readonly=True)
    status = fields.Selection([
        ("pending_claim", "Pending claim"),
        ("active", "Active"),
        ("disabled", "Disabled"),
    ], default="pending_claim")
    is_online = fields.Boolean(readonly=True)
    last_seen_at = fields.Datetime(readonly=True)
    location = fields.Char()
    timezone = fields.Char()
