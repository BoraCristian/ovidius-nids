let _token = '';
export function setAuthToken(tok) { _token = tok || ''; }
export function getAuthToken() { return _token; }

async function request(method, url, body, opts = {}) {
  const headers = {
    Accept: 'application/json',
    ...(body && !(body instanceof URLSearchParams) ? { 'Content-Type': 'application/json' } : {}),
    ...(opts.headers || {}),
  };
  if (_token) headers.Authorization = `Bearer ${_token}`;

  const res = await fetch(url, {
    method,
    headers,
    body: body ? (body instanceof URLSearchParams ? body : JSON.stringify(body)) : undefined,
  });
  const isJson = (res.headers.get('content-type') || '').includes('application/json');
  const data = isJson ? await res.json().catch(() => null) : await res.text();
  if (!res.ok) {
    const msg = (data && data.detail) || res.statusText || `HTTP ${res.status}`;
    const err = new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const apiGet    = (u, o)    => request('GET',    u, null, o);
export const apiPost   = (u, b, o) => request('POST',   u, b,    o);
export const apiPatch  = (u, b, o) => request('PATCH',  u, b,    o);
export const apiDelete = (u, o)    => request('DELETE', u, null, o);

/**
 * Authenticated file download.
 *
 * A plain `<a href="/protected" download>` can't attach the `Authorization`
 * header, so the server replies 401 and Chrome shows "File wasn't available
 * on site".  This helper fetches the bytes with the JWT attached, wraps the
 * response in a Blob URL, and triggers a hidden anchor click so the browser
 * saves the file normally.
 */
export async function apiDownload(url, suggestedName) {
  const headers = { Accept: 'application/octet-stream' };
  if (_token) headers.Authorization = `Bearer ${_token}`;
  const res = await fetch(url, { headers });
  if (!res.ok) {
    const msg = res.statusText || `HTTP ${res.status}`;
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }

  // Prefer the filename the server suggested in Content-Disposition.
  let filename = suggestedName || 'download';
  const cd = res.headers.get('content-disposition') || '';
  const m = /filename\*?="?([^;"]+)"?/i.exec(cd);
  if (m && m[1]) filename = decodeURIComponent(m[1].replace(/^UTF-8''/, ''));

  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoke a tick later so Chrome has time to read the blob.
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

/** Open a WebSocket to a backend path with the JWT embedded in the query string. */
export function openWebSocket(path) {
  const base = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}`;
  const sep  = path.includes('?') ? '&' : '?';
  return new WebSocket(`${base}${path}${sep}token=${encodeURIComponent(_token)}`);
}
