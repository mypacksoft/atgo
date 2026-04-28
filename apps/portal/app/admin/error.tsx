"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string; status?: number };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[admin error]", error);
  }, [error]);

  const status = (error as any).status as number | undefined;
  const isAuth = status === 401 || status === 403;

  return (
    <div className="center" style={{ padding: "2rem" }}>
      <div className="card" style={{ width: "min(560px, 92vw)" }}>
        <h2 style={{ marginTop: 0 }}>
          {isAuth ? "Not authorized" : "Admin error"}
        </h2>
        <p className="muted">
          {isAuth
            ? "Your session expired or you're not a super-admin. Sign in again with an admin account."
            : (error?.message || "Unknown error")}
        </p>
        <div className="row" style={{ marginTop: "1rem" }}>
          {isAuth ? (
            <Link href="/login" className="btn">Sign in</Link>
          ) : (
            <button className="btn" onClick={() => reset()}>Retry</button>
          )}
          <Link href="/" className="btn secondary">Home</Link>
        </div>
      </div>
    </div>
  );
}
