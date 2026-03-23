/**
 * Call backend API (Vite proxies /api to FastAPI).
 * Set VITE_API_KEY in frontend/.env.local to match backend API_KEY.
 */

const apiKey = import.meta.env.VITE_API_KEY ?? "";

export async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(apiKey ? { "X-API-Key": apiKey } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}
