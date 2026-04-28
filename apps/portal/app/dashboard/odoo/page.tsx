"use client";
export default function OdooPage() {
  return (
    <div className="grid">
      <div className="card">
        <h2>Odoo integration</h2>
        <p className="muted">
          ATGO ships a free Odoo module that syncs attendance into <code className="kbd">hr.attendance</code>.
        </p>
        <ol style={{ lineHeight: 1.7 }}>
          <li>In Odoo, install the <strong>ATGO Connector</strong> module from your Odoo Apps catalog.</li>
          <li>Open <strong>Settings → ATGO</strong> in Odoo.</li>
          <li>Set <strong>Gateway URL</strong> to <code className="kbd">https://api.atgo.io</code>.</li>
          <li>Create an API key in <a href="/dashboard/api-keys">API keys</a> and paste it into Odoo.</li>
          <li>Click <em>Test connection</em>. The cron will pull logs every minute.</li>
        </ol>
      </div>

      <div className="card">
        <h3>What it does</h3>
        <ul style={{ lineHeight: 1.8 }}>
          <li>Pulls unsynced punches from <code className="kbd">/api/odoo/attendance-logs</code></li>
          <li>Creates <code className="kbd">hr.attendance</code> rows mapped by employee PIN</li>
          <li>Acks logs back via <code className="kbd">/api/odoo/attendance-logs/ack</code></li>
          <li>Reports sync errors back to ATGO</li>
          <li>Optionally: sync employees from Odoo up to ATGO</li>
        </ul>
      </div>
    </div>
  );
}
