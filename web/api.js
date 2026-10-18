export async function api(path, values, method = "POST") {
  const response = await fetch(
    path,
    values === undefined
      ? {}
      : {
          method,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(values),
        },
  );
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error("Server returned an unreadable response");
  }
  if (!response.ok)
    throw new Error(
      data.error || data.message || `Request failed (${response.status})`,
    );
  return data;
}
export function safeURL(value) {
  try {
    const u = new URL(value);
    return ["https:", "http:"].includes(u.protocol) ? u.href : "#";
  } catch {
    return "#";
  }
}
