import { leerAvisos, setup, umbrales } from "./avisos.js";

export { setup };

export const options = {
  vus: 10,
  duration: "15m",
  thresholds: umbrales,
};

export default function (data) {
  leerAvisos(data);
}
