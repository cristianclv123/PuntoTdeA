import { leerCasos, setup, umbrales } from "./casos.js";

export { setup };

export const options = {
  stages: [
    { duration: "30s", target: 10 },
    { duration: "1m", target: 50 },
    { duration: "1m", target: 50 },
    { duration: "1m", target: 100 },
    { duration: "1m", target: 100 },
    { duration: "30s", target: 0 },
  ],
  thresholds: umbrales,
};

export default function (data) {
  leerCasos(data);
}
