#!/usr/bin/env node
// Reads the design tokens out of src/index.css and re-derives the contrast and
// colour-blindness tables the design spec claims. Exits non-zero on any failure.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const CSS = process.argv[2] ?? resolve(HERE, "..", "src", "index.css");

// ---------------------------------------------------------------- colour maths

function oklchToLinear(L, C, hDeg) {
  const h = (hDeg * Math.PI) / 180;
  const a = C * Math.cos(h);
  const b = C * Math.sin(h);
  const l_ = L + 0.3963377774 * a + 0.2158037573 * b;
  const m_ = L - 0.1055613458 * a - 0.0638541728 * b;
  const s_ = L - 0.0894841775 * a - 1.291485548 * b;
  const l = l_ ** 3, m = m_ ** 3, s = s_ ** 3;
  return [
    4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
    -0.0041960863 * l - 0.7034186147 * m + 1.707614701 * s,
  ];
}

const encode = (c) => {
  const v = Math.min(1, Math.max(0, c));
  return v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055;
};

const hex = (lin) =>
  "#" + lin.map((c) => Math.round(encode(c) * 255).toString(16).padStart(2, "0").toUpperCase()).join("");

const decode = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);

// A tint composites over its surface in gamma space, which is where the browser does it.
const over = (tint, alpha, surface) => {
  const f = tint.map(encode);
  const b = surface.map(encode);
  return f.map((c, i) => decode(alpha * c + (1 - alpha) * b[i]));
};

const luminance = (lin) => {
  const [r, g, b] = lin.map((c) => Math.min(1, Math.max(0, c)));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

// Viénot/Brettel/Mollon 1999 dichromat simulation, applied on LINEAR rgb.
const CVD = {
  protan: [[0.11238, 0.88762, 0.0], [0.11238, 0.88762, 0.0], [0.00401, -0.00401, 1.0]],
  deutan: [[0.29275, 0.70725, 0.0], [0.29275, 0.70725, 0.0], [-0.02234, 0.02234, 1.0]],
  normal: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
};

const applyCvd = (lin, kind) =>
  CVD[kind].map((row) => row[0] * lin[0] + row[1] * lin[1] + row[2] * lin[2]);

const M_XYZ = [
  [0.4123908, 0.3575843, 0.1804808],
  [0.2126390, 0.7151687, 0.0721923],
  [0.0193308, 0.1191948, 0.9505322],
];
const WHITE = [0.9504559, 1.0, 1.0890578];

function toLab(lin) {
  const c = lin.map((v) => Math.min(1, Math.max(0, v)));
  const xyz = M_XYZ.map((row) => row[0] * c[0] + row[1] * c[1] + row[2] * c[2]);
  const f = xyz.map((v, i) => {
    const t = v / WHITE[i];
    return t > 216 / 24389 ? Math.cbrt(t) : (841 / 108) * t + 4 / 29;
  });
  return [116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])];
}

function deltaE(a, b, kind) {
  const [la, aa, ba] = toLab(applyCvd(a, kind));
  const [lb, ab, bb] = toLab(applyCvd(b, kind));
  return Math.hypot(la - lb, aa - ab, ba - bb);
}

// ---------------------------------------------------------------- css parsing

const source = readFileSync(CSS, "utf8");

function block(re) {
  const found = source.match(re);
  if (!found) throw new Error(`no encontrado en ${CSS}: ${re}`);
  return found[1];
}

function tokensIn(text) {
  const out = {};
  for (const [, name, L, C, H] of text.matchAll(
    /(--[\w-]+)\s*:\s*oklch\(\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\)/g,
  )) {
    out[name] = oklchToLinear(Number(L), Number(C), Number(H));
  }
  return out;
}

const lightSrc = block(/:root\s*\{([\s\S]*?)\n\}/);
const darkSrc = block(/:root\[data-theme="dark"\]\s*\{([\s\S]*?)\n\}/);
const light = tokensIn(lightSrc);
const dark = { ...light, ...tokensIn(darkSrc) };

// ---------------------------------------------------------------- the claims

const TEXT = [
  "--foreground",
  "--muted-foreground",
  "--primary",
  "--attention",
  "--settled",
  "--destructive",
  "--code-string",
  "--code-number",
];
const SURFACES = ["--background", "--card"];
// A separator carries no information, so WCAG asks nothing of it; a control outline does.
const OUTLINE = { "--input": 3, "--border": 1.3 };
const SEMANTIC = ["--primary", "--attention", "--settled", "--destructive"];

// Text on a tint of ITS OWN hue. This is the case the plain contrast table cannot see and
// that it missed: a badge paints its colour behind its own label, so the tint eats the
// margin the token was verified at. At 18 % the settled and attention badges measured 4.32
// and 4.26 in light mode — under the floor, on the badge that reports every stage's state.
const TINTED = [
  ["--primary", 0.08],
  ["--attention", 0.08],
  ["--settled", 0.08],
  ["--destructive", 0.08],
];

// EVERY `--X-foreground` AGAINST ITS `--X`. This is the pair the tables above cannot see:
// they check a colour used as TEXT on the page's surfaces, and a foreground token is the
// opposite case — the label that sits ON the colour. Added 2026-09-01, after a button
// shipped a near-white label on a token that is a LIGHT colour in dark mode: 1.72:1, and
// close enough on both sides that it read as a styling choice.
// Derived from the token names rather than listed, so a new pair is covered by existing.
const TEXT_MIN = 4.5;
const DE_MIN = 15;

let failures = 0;
const fail = (line) => { failures++; console.log(`  FALLA  ${line}`); };
const ok = (line) => console.log(`  ok     ${line}`);

for (const [mode, tokens] of [["claro", light], ["oscuro", dark]]) {
  console.log(`\n== ${mode} ==`);

  for (const name of TEXT) {
    if (!tokens[name]) { fail(`${name} no existe`); continue; }
    const ratios = SURFACES.map((s) => contrast(tokens[name], tokens[s]));
    const line = `${name.padEnd(20)} ${hex(tokens[name])}  ${ratios.map((r) => r.toFixed(2)).join(" / ")}`;
    Math.min(...ratios) >= TEXT_MIN ? ok(line) : fail(`${line}  < ${TEXT_MIN}`);
  }

  for (const [name, alpha] of TINTED) {
    if (!tokens[name]) continue;
    const ratio = contrast(tokens[name], over(tokens[name], alpha, tokens["--card"]));
    const line = `${name.padEnd(20)} sobre su tinte al ${(alpha * 100).toFixed(0)}%  ${ratio.toFixed(2)}`;
    ratio >= TEXT_MIN ? ok(line) : fail(`${line}  < ${TEXT_MIN}`);
  }

  for (const name of Object.keys(tokens).filter((n) => n.endsWith("-foreground"))) {
    const ground = name.slice(0, -"-foreground".length);
    // `--foreground` and `--muted-foreground` name no ground of their own; the TEXT table
    // above is what covers those.
    if (!tokens[ground]) continue;
    const ratio = contrast(tokens[name], tokens[ground]);
    const line = `${name.padEnd(20)} sobre ${ground}  ${ratio.toFixed(2)}`;
    ratio >= TEXT_MIN ? ok(line) : fail(`${line}  < ${TEXT_MIN}`);
  }

  for (const [name, min] of Object.entries(OUTLINE)) {
    if (!tokens[name]) { fail(`${name} no existe`); continue; }
    const ratio = contrast(tokens[name], tokens["--background"]);
    const line = `${name.padEnd(20)} ${hex(tokens[name])}  ${ratio.toFixed(2)} (mín ${min})`;
    ratio >= min ? ok(line) : fail(`${line}`);
  }

  for (const kind of ["normal", "deutan", "protan"]) {
    for (let i = 0; i < SEMANTIC.length; i++) {
      for (let j = i + 1; j < SEMANTIC.length; j++) {
        const [a, b] = [SEMANTIC[i], SEMANTIC[j]];
        if (!tokens[a] || !tokens[b]) continue;
        const d = deltaE(tokens[a], tokens[b], kind);
        const line = `ΔE ${kind.padEnd(6)} ${a.slice(2)} vs ${b.slice(2)}: ${d.toFixed(1)}`;
        d >= DE_MIN ? ok(line) : fail(`${line} < ${DE_MIN}`);
      }
    }
  }
}

console.log(failures === 0 ? "\nTodo pasa.\n" : `\n${failures} comprobación(es) fallan.\n`);
process.exit(failures === 0 ? 0 : 1);
