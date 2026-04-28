"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[ATGO error boundary]", error);
  }, [error]);

  return (
    <div className="center" style={{ padding: "2rem" }}>
      <div className="card" style={{ width: "min(640px, 92vw)" }}>
        <h2 style={{ marginTop: 0 }}>Something went wrong</h2>
        <p className="muted">{error?.message || "Unknown error"}</p>
        {error?.digest && (
          <p className="muted" style={{ fontSize: "0.75rem" }}>id: {error.digest}</p>
        )}
        <div className="row" style={{ marginTop: "1rem" }}>
          <button className="btn" onClick={() => reset()}>Try again</button>
          <a className="btn secondary" href="/">Home</a>
        </div>
      </div>
    </div>
  );
}
