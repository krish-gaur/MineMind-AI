// Builds public/geo/countries-context.geojson from the public-domain Natural Earth 110m countries
// (packaged by the world-atlas npm module). Run once: `npm run build:basemap`. The output is committed.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const topojson = require("topojson-client");
const here = dirname(fileURLToPath(import.meta.url));
const world = JSON.parse(readFileSync(require.resolve("world-atlas/countries-110m.json"), "utf8"));
const countries = topojson.feature(world, world.objects.countries);

// Context window: South Asia and neighbours. Only countries that intersect it are kept.
const WINDOW = { minLon: 55, maxLon: 105, minLat: 0, maxLat: 45 };

function bounds(geometry) {
  let minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
  const visit = (node) => {
    if (typeof node[0] === "number") {
      minLon = Math.min(minLon, node[0]);
      maxLon = Math.max(maxLon, node[0]);
      minLat = Math.min(minLat, node[1]);
      maxLat = Math.max(maxLat, node[1]);
    } else {
      node.forEach(visit);
    }
  };
  if (geometry.coordinates) visit(geometry.coordinates);
  return { minLon, minLat, maxLon, maxLat };
}

function round(node) {
  return typeof node[0] === "number" ? [Math.round(node[0] * 1000) / 1000, Math.round(node[1] * 1000) / 1000] : node.map(round);
}

const kept = countries.features
  .filter((feature) => {
    const b = bounds(feature.geometry);
    return b.maxLon >= WINDOW.minLon && b.minLon <= WINDOW.maxLon && b.maxLat >= WINDOW.minLat && b.minLat <= WINDOW.maxLat;
  })
  .map((feature) => ({
    type: "Feature",
    properties: { name: feature.properties?.name ?? "" },
    geometry: { type: feature.geometry.type, coordinates: round(feature.geometry.coordinates) },
  }));

const output = resolve(here, "../public/geo/countries-context.geojson");
mkdirSync(dirname(output), { recursive: true });
writeFileSync(
  output,
  JSON.stringify({
    type: "FeatureCollection",
    name: "countries-context",
    attribution: "Made with Natural Earth (public domain). Packaged by world-atlas.",
    features: kept,
  }),
);
console.log(`Wrote ${kept.length} country features to ${output}`);
