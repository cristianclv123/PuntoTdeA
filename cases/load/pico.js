import { leerCasos, setup, umbrales } from "./casos.js";

export { setup };

export const options = {
  stages: [
    { duration: "20s", target: 5 },
    { duration: "10s", target: 40 },
    { duration: "20s", target: 40 },
    { duration: "10s", target: 5 },
    { duration: "20s", target: 5 },
  ],
  thresholds: umbrales,
};

export default function (data) {
  leerCasos(data);
}
