/* Marketing landing — atgo.io. */
import Link from "next/link";

export default function LandingPage() {
  return (
    <main>
      <header className="nav">
        <strong>ATGO</strong>
        <span className="muted">Cloud Attendance for ZKTeco</span>
        <span className="right row">
          <Link href="/pricing">Pricing</Link>
          <Link href="/login">Sign in</Link>
          <Link href="/signup" className="btn" style={{ padding: "0.45rem 0.9rem", color: "white", display: "inline-block" }}>
            Start free
          </Link>
        </span>
      </header>

      <section className="content" style={{ paddingTop: "4rem", textAlign: "center" }}>
        <h1 style={{ fontSize: "2.6rem", lineHeight: 1.1 }}>
          Free online attendance for ZKTeco — no static IP, no port forwarding, no local server.
        </h1>
        <p className="muted" style={{ fontSize: "1.15rem", maxWidth: 760, margin: "1rem auto" }}>
          Plug your ZKTeco device into ATGO Cloud, manage employees online, and ship attendance
          straight into Odoo HR. Free for 1 device. Unlimited employees. Custom domain on Business.
        </p>
        <div className="row" style={{ justifyContent: "center", marginTop: "1.5rem" }}>
          <Link href="/signup" className="btn" style={{ color: "white", padding: "0.75rem 1.4rem", borderRadius: 8, display: "inline-block" }}>
            Create free workspace
          </Link>
          <Link href="/pricing" className="btn secondary" style={{ padding: "0.75rem 1.4rem", borderRadius: 8, display: "inline-block" }}>
            See pricing
          </Link>
        </div>
      </section>

      <section className="content">
        <div className="grid cols-3" style={{ marginTop: "3rem" }}>
          <div className="card">
            <h3>Cloud sync, no headaches</h3>
            <p className="muted">
              Point your ZKTeco device at <span className="kbd">atgo.io/&lt;CODE&gt;</span> and it streams
              attendance to your workspace in seconds. No VPN. No DDNS.
            </p>
          </div>
          <div className="card">
            <h3>Odoo HR included</h3>
            <p className="muted">
              Install the open-source Odoo plugin, paste an API key, and let
              ATGO push <span className="kbd">hr.attendance</span> records into Odoo 16/17/18.
            </p>
          </div>
          <div className="card">
            <h3>Employee self-service</h3>
            <p className="muted">
              Each employee gets a PWA where they can view their own timesheet,
              spot missing punches, and request corrections.
            </p>
          </div>
          <div className="card">
            <h3>Custom domain</h3>
            <p className="muted">
              On Business and above, attach <span className="kbd">attendance.yourcompany.com</span> to your
              workspace. Cloudflare auto-DNS available on HR Pro.
            </p>
          </div>
          <div className="card">
            <h3>Multi-device sync</h3>
            <p className="muted">
              Manage employees online and push them to many devices at once.
              Biometric data is never stored on our servers.
            </p>
          </div>
          <div className="card">
            <h3>Privacy first</h3>
            <p className="muted">
              We strip USERPIC / FACE / FP / BIODATA / FINGERTMP / ATTPHOTO before
              they hit the database. Tenant isolation enforced via Postgres RLS.
            </p>
          </div>
        </div>
      </section>

      <section className="content" style={{ marginTop: "3rem", marginBottom: "3rem" }}>
        <div className="card">
          <h2>How it works</h2>
          <ol className="muted" style={{ lineHeight: 1.8 }}>
            <li>Create your free workspace at <span className="kbd">yourcompany.atgo.io</span>.</li>
            <li>Add a device — we generate a 4-character code like <span className="kbd">A7K9</span>.</li>
            <li>On the ZKTeco device, set Cloud Server = <span className="kbd">atgo.io/A7K9</span>.</li>
            <li>Confirm the claim code in your portal — punches start flowing.</li>
            <li>Optional: install the Odoo plugin and connect via API key.</li>
          </ol>
        </div>
      </section>

      <footer className="content muted" style={{ borderTop: "1px solid var(--border)", paddingTop: "1rem" }}>
        © {new Date().getFullYear()} ATGO. Free online attendance for ZKTeco devices.
      </footer>
    </main>
  );
}
