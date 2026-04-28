"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type Plan = {
  id: string;
  name: string;
  monthly_price_usd_cents: number;
  device_limit: number | null;
  employee_limit: number | null;
  log_retention_days: number;
  monthly_log_quota: number | null;
  allow_custom_domain: boolean;
  custom_domain_limit: number;
  allow_auto_dns: boolean;
  allow_advanced_rules: boolean;
  is_public: boolean;
};

const FIELDS: Array<[keyof Plan, string, "int" | "bool"]> = [
  ["monthly_price_usd_cents", "Price (USD cents)", "int"],
  ["device_limit", "Device limit", "int"],
  ["employee_limit", "Employee limit", "int"],
  ["log_retention_days", "Log retention (days)", "int"],
  ["monthly_log_quota", "Monthly log quota", "int"],
  ["custom_domain_limit", "Custom domain limit", "int"],
  ["allow_custom_domain", "Allow custom domain", "bool"],
  ["allow_auto_dns", "Allow auto DNS", "bool"],
  ["allow_advanced_rules", "Allow advanced rules", "bool"],
  ["is_public", "Public", "bool"],
];

export default function AdminPlansPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [editing, setEditing] = useState<Plan | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  async function load() { setPlans(await api.get<Plan[]>("/api/admin/plans")); }
  useEffect(() => { load(); }, []);

  async function save() {
    if (!editing) return;
    setSaving(true);
    try {
      const body: any = {};
      for (const [k] of FIELDS) body[k] = (editing as any)[k];
      await api.patch(`/api/admin/plans/${editing.id}`, body);
      setMsg("Saved");
      setEditing(null);
      load();
    } catch (e: any) {
      setMsg(e?.message || "save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid">
      <h1>Plans</h1>
      <p className="muted">Edit pricing and limits. Changes take effect immediately for new subscriptions.</p>
      {msg && <div className="okbox">{msg}</div>}

      <div className="grid cols-2">
        {plans.map((p) => (
          <div className="card" key={p.id}>
            <div className="row" style={{ alignItems: "baseline" }}>
              <h3 style={{ margin: 0 }}>{p.name}</h3>
              <span className="muted">id: {p.id}</span>
              {!p.is_public && <span className="badge">hidden</span>}
            </div>
            <p style={{ fontSize: "1.4rem", margin: "0.4rem 0" }}>
              ${(p.monthly_price_usd_cents / 100).toFixed(2)}<span className="muted">/mo</span>
            </p>
            <ul className="muted" style={{ lineHeight: 1.6, paddingLeft: "1rem" }}>
              <li>{p.device_limit ?? "∞"} devices</li>
              <li>{p.employee_limit ?? "∞"} employees</li>
              <li>{p.log_retention_days} day retention · {p.monthly_log_quota ?? "∞"} logs/mo quota</li>
              <li>Custom domain: {p.allow_custom_domain ? `up to ${p.custom_domain_limit}` : "no"}</li>
              <li>Auto DNS: {p.allow_auto_dns ? "yes" : "no"} · Advanced rules: {p.allow_advanced_rules ? "yes" : "no"}</li>
            </ul>
            <button className="btn secondary" onClick={() => setEditing({ ...p })}>Edit</button>
          </div>
        ))}
      </div>

      {editing && (
        <div className="card" style={{ borderColor: "var(--accent)" }}>
          <h3>Edit {editing.name} ({editing.id})</h3>
          <div className="grid cols-2">
            {FIELDS.map(([k, label, type]) => (
              <label key={String(k)}>
                {label}
                {type === "bool" ? (
                  <input type="checkbox"
                         checked={Boolean((editing as any)[k])}
                         onChange={(e) => setEditing({ ...editing, [k]: e.target.checked } as Plan)} />
                ) : (
                  <input type="number"
                         value={(editing as any)[k] ?? ""}
                         onChange={(e) => setEditing({
                           ...editing,
                           [k]: e.target.value === "" ? null : Number(e.target.value),
                         } as Plan)} />
                )}
              </label>
            ))}
          </div>
          <div className="row" style={{ marginTop: "1rem" }}>
            <button className="btn" onClick={save} disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button className="btn secondary" onClick={() => setEditing(null)}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  );
}
