import { leerCasos, setup, umbrales } from "./casos.js";

export { setup };

export const options = {
  vus: 1,
  duration: "30s",
  thresholds: umbrales,
};

export default function (data) {
  leerCasos(data);
}
