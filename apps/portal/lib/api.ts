/* Lightweight API client. Uses Next.js rewrites — paths start with /api. */

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message || `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
  }
}

function getToken(kind: "hr" | "emp"): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(kind === "hr" ? "atgo_token" : "atgo_emp_token");
}

export function setToken(kind: "hr" | "emp", token: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(kind === "hr" ? "atgo_token" : "atgo_emp_token", token);
}

export function clearToken(kind: "hr" | "emp") {
  if (typeof window === "undefined") return;
  localStorage.removeItem(kind === "hr" ? "atgo_token" : "atgo_emp_token");
}

async function request<T>(
  path: string,
  opts: RequestInit = {},
  kind: "hr" | "emp" = "hr",
): Promise<T> {
  const token = getToken(kind);
  const headers = new Headers(opts.headers || {});
  if (!headers.has("Content-Type") && opts.body && typeof opts.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(path, { ...opts, headers, cache: "no-store" });
  } catch (e: any) {
    throw new ApiError(0, e?.message || "network error");
  }

  if (!res.ok) {
    let message = res.statusText || `HTTP ${res.status}`;
    try {
      const j = await res.json();
      message = j.detail || j.error || j.message || message;
      if (Array.isArray(message)) {
        // Pydantic validation errors come back as array of {msg, loc, type}
        message = message.map((m: any) => m?.msg || JSON.stringify(m)).join("; ");
      } else if (typeof message === "object") {
        message = JSON.stringify(message);
      }
    } catch {
      /* swallow — body wasn't json */
    }

    // Auto-redirect to /login on auth failure (only on the client)
    if (res.status === 401 && typeof window !== "undefined") {
      const onAuthPage = /\/(login|signup)(\/|$)/.test(window.location.pathname);
      if (!onAuthPage) {
        clearToken(kind);
        const next = encodeURIComponent(window.location.pathname + window.location.search);
        window.location.replace(`/login?next=${next}`);
      }
    }

    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as unknown as T;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}

export const api = {
  get:    <T,>(p: string, kind?: "hr" | "emp") => request<T>(p, { method: "GET" }, kind),
  post:   <T,>(p: string, body?: unknown, kind?: "hr" | "emp") =>
    request<T>(p, { method: "POST", body: body ? JSON.stringify(body) : undefined }, kind),
  patch:  <T,>(p: string, body?: unknown, kind?: "hr" | "emp") =>
    request<T>(p, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }, kind),
  delete: <T,>(p: string, kind?: "hr" | "emp") => request<T>(p, { method: "DELETE" }, kind),
};

/** Tenant slug that matches the current host, or undefined when on api/admin host. */
export function tenantSlugFromHost(host: string, baseDomain: string): string | undefined {
  const h = host.split(":")[0].toLowerCase();
  if (!h.endsWith("." + baseDomain)) return undefined;
  const slug = h.slice(0, -(baseDomain.length + 1));
  if (!slug || ["www", "api", "admin", "adms", "cname"].includes(slug)) return undefined;
  return slug;
}
