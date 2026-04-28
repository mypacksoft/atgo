============================================
ATGO Connect — ZKTeco Cloud Attendance
============================================

.. |badge1| image:: https://img.shields.io/badge/licence-OPL--1-blueviolet.png
    :target: https://www.odoo.com/documentation/19.0/legal/licenses.html#odoo-apps
.. |badge2| image:: https://img.shields.io/badge/odoo-16%20|%2017%20|%2018%20|%2019-714B67.svg
.. |badge3| image:: https://img.shields.io/badge/price-%2419-success.svg

|badge1| |badge2| |badge3|

Free online attendance system for ZKTeco devices, integrated into Odoo HR.

This module connects your Odoo HR with `ATGO Cloud`_, a free attendance
platform that lets your ZKTeco devices stream punches to the cloud over the
internet — no static IP, no port forwarding, no local Windows PC.

Odoo polls ATGO every 5 minutes (outbound), creates ``hr.attendance``
records, and acknowledges them so they aren't fetched twice.

.. _ATGO Cloud: https://atgo.io


Features
========

* Pull attendance logs from ATGO Cloud, create ``hr.attendance``
* Map device PIN to ``hr.employee.barcode``
* Optional employee push from Odoo to ATGO (one-way sync)
* Cron-driven (5-minute default, configurable)
* Fully outbound — no inbound network port required on the Odoo host
* Strips ZKTeco biometric data (USERPIC / FACE / FP / BIODATA) at the
  ATGO edge — never reaches Odoo


Configuration
=============

#. Install the module.
#. Sign up at https://atgo.io and create a workspace.
#. In ATGO portal → Settings → API keys → generate one.
#. In Odoo: **ATGO → Settings**.
#. Fill in *Workspace slug*, *API base URL*
   (default ``https://api.atgo.io``), and the API key.
#. Click **Test connection**. You should see your plan + device count.
#. Cron ``ATGO: pull attendance logs`` runs every 5 minutes by default.

Map employees by setting ``hr.employee.barcode`` to the device PIN
configured on the ZKTeco device. Unmapped PINs are stored in
``atgo.attendance.log`` with state *skipped* so you can fix them later.


Usage
=====

* Manage attendances from Odoo as usual (``hr.attendance``)
* View raw pulled logs under **ATGO → Attendance logs**
* Re-process skipped logs after fixing employee barcodes


Compatibility
=============

This branch targets **Odoo 19.0**. Branches for 16.0, 17.0, 18.0 are
maintained in parallel.


Bug Tracker
===========

Report issues at https://github.com/atgo-io/atgo-odoo-connect/issues.

For security issues, email security@atgo.io rather than opening a public issue.


Credits
=======

Authors
~~~~~~~

* ATGO (https://atgo.io)


Maintainers
~~~~~~~~~~~

This module is maintained by ATGO.

License
~~~~~~~

This module is licensed under the **Odoo Proprietary License v1.0 (OPL-1)**.

Buy a license from the Odoo Apps Store ($19): https://apps.odoo.com/apps/modules/19.0/atgo_connect/

The fee is per Odoo database. The accompanying ATGO Cloud platform itself is
free for 1 ZKTeco device — pricing for additional devices and HR features is
on https://atgo.io/pricing.
