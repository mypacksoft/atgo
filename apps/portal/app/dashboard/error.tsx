"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { status?: number };
  reset: () => void;
}) {
  useEffect(() => { console.error("[dashboard error]", error); }, [error]);

  const status = (error as any).status as number | undefined;
  const isAuth = status === 401 || status === 403;

  return (
    <div className="center" style={{ padding: "2rem" }}>
      <div className="card" style={{ width: "min(560px, 92vw)" }}>
        <h2 style={{ marginTop: 0 }}>{isAuth ? "Please sign in" : "Something went wrong"}</h2>
        <p className="muted">{isAuth ? "Your session expired." : (error?.message || "Unknown error")}</p>
        <div className="row" style={{ marginTop: "1rem" }}>
          {isAuth
            ? <Link href="/login" className="btn">Sign in</Link>
            : <button className="btn" onClick={() => reset()}>Retry</button>}
          <Link href="/" className="btn secondary">Home</Link>
        </div>
      </div>
    </div>
  );
}
