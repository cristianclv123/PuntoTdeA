import { leerAvisos, setup, umbrales } from "./avisos.js";

export { setup };

export const options = {
  vus: 1,
  duration: "30s",
  thresholds: umbrales,
};

export default function (data) {
  leerAvisos(data);
}
