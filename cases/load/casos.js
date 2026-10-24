import http from "k6/http";
import { check, sleep } from "k6";

export const BASE = __ENV.K6_BASE || "http://127.0.0.1:8000";

export const umbrales = {
  http_req_failed: ["rate<0.01"],
  http_req_duration: ["p(95)<500"],
};

export function setup() {
  const page = http.get(`${BASE}/login/`);
  const csrf = page.cookies.csrftoken && page.cookies.csrftoken[0].value;
  const login = http.post(
    `${BASE}/login/`,
    {
      username: __ENV.K6_USER || "",
      password: __ENV.K6_PASSWORD || "",
      csrfmiddlewaretoken: csrf,
    },
    {
      headers: { Referer: `${BASE}/login/` },
      redirects: 0,
    }
  );
  check(login, { "login redirige": (r) => r.status === 302 });
  const session = login.cookies.sessionid && login.cookies.sessionid[0].value;
  return { csrf, session };
}

export function leerCasos(data) {
  const jar = http.cookieJar();
  jar.set(BASE, "csrftoken", data.csrf);
  jar.set(BASE, "sessionid", data.session);

  const bandeja = http.get(`${BASE}/bandeja/`);
  const tickets = http.get(`${BASE}/api/cases/tickets/`);
  const departments = http.get(`${BASE}/api/cases/departments/`);

  check(bandeja, { "bandeja 200": (r) => r.status === 200 });
  check(tickets, { "tickets 200": (r) => r.status === 200 });
  check(departments, { "dependencias 200": (r) => r.status === 200 });

  let rows = [];
  try {
    const body = tickets.json();
    rows = Array.isArray(body) ? body : body.results || [];
  } catch (_) {
    rows = [];
  }
  if (rows.length) {
    const messages = http.get(
      `${BASE}/api/cases/messages/?conversation=${rows[0].id}`
    );
    check(messages, { "mensajes 200": (r) => r.status === 200 });
  }

  sleep(1);
}
