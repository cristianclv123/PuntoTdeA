import { leerCasos, setup, umbrales } from "./casos.js";

export { setup };

export const options = {
  vus: 10,
  duration: "2m",
  thresholds: umbrales,
};

export default function (data) {
  leerCasos(data);
}
