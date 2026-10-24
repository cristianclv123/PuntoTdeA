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

export function leerAvisos(data) {
  const jar = http.cookieJar();
  jar.set(BASE, "csrftoken", data.csrf);
  jar.set(BASE, "sessionid", data.session);

  const avisos = http.get(`${BASE}/avisos/`);
  check(avisos, { "avisos 200": (r) => r.status === 200 });

  const match = String(avisos.body || "").match(/\/avisos\/imagen\/(\d+)\//);
  if (match) {
    const image = http.get(`${BASE}/avisos/imagen/${match[1]}/`);
    check(image, { "imagen 200": (r) => r.status === 200 });
  }

  sleep(1);
}
