"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

type Settings = {
  auto_create_from_machine: boolean;
  auto_create_from_odoo: boolean;
  work_week_days: number;
  standard_shift_minutes: number;
};

export default function SettingsPage() {
  const [s, setS] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => { api.get<Settings>("/api/me/settings").then(setS); }, []);

  async function save() {
    if (!s) return;
    setSaving(true); setMsg("");
    try {
      const r = await api.patch<Settings>("/api/me/settings", s);
      setS(r); setMsg("Saved ✓");
    } catch (e: any) { setMsg(e?.message || "save failed"); }
    finally { setSaving(false); }
  }

  if (!s) return <div className="muted">Loading…</div>;

  return (
    <div className="grid">
      <div className="card">
        <h2>Workspace settings</h2>
        <p className="muted">Áp dụng cho toàn bộ tenant của bạn.</p>
      </div>

      <div className="card">
        <h3>Đồng bộ tự động</h3>
        <p className="muted" style={{ fontSize: "0.85rem" }}>
          Khi bật, ATGO tự tạo nhân viên placeholder thay vì bỏ qua dữ liệu.
        </p>
        <label className="row" style={{ alignItems: "center", marginTop: "0.5rem" }}>
          <input type="checkbox" checked={s.auto_create_from_machine}
            onChange={(e) => setS({ ...s, auto_create_from_machine: e.target.checked })} />
          <span>
            <strong>Tự tạo nhân viên từ máy chấm công</strong>
            <div className="muted" style={{ fontSize: "0.8rem" }}>
              Khi máy gửi log với PIN chưa có trong danh sách → tạo nhân viên mới
              tên "Unknown PIN xxx". HR có thể đổi tên sau.
            </div>
          </span>
        </label>
        <label className="row" style={{ alignItems: "center", marginTop: "0.8rem" }}>
          <input type="checkbox" checked={s.auto_create_from_odoo}
            onChange={(e) => setS({ ...s, auto_create_from_odoo: e.target.checked })} />
          <span>
            <strong>Tự tạo nhân viên từ Odoo</strong>
            <div className="muted" style={{ fontSize: "0.8rem" }}>
              Khi Odoo plugin push <code>hr.employee</code> mới → tạo trong ATGO
              với <code>odoo_id</code> link 2 chiều.
            </div>
          </span>
        </label>
      </div>

      <div className="card">
        <h3>Lịch làm việc</h3>
        <div className="grid cols-2">
          <label>
            Số ngày làm việc / tuần
            <select value={s.work_week_days}
              onChange={(e) => setS({ ...s, work_week_days: Number(e.target.value) })}>
              <option value={5}>5 (Mon-Fri)</option>
              <option value={6}>6 (Mon-Sat)</option>
              <option value={7}>7 (cả tuần)</option>
            </select>
          </label>
          <label>
            Ca chuẩn (phút/ngày)
            <input type="number" min={60} max={1440} value={s.standard_shift_minutes}
              onChange={(e) => setS({ ...s, standard_shift_minutes: Number(e.target.value) })} />
          </label>
        </div>
      </div>

      <div className="row">
        <button className="btn" onClick={save} disabled={saving}>
          {saving ? "Đang lưu…" : "Save"}
        </button>
        {msg && <span className={msg.includes("✓") ? "" : "muted"}>{msg}</span>}
      </div>
    </div>
  );
}
