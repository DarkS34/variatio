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
const darkSrc = block(/prefers-color-scheme:\s*dark\s*\)\s*\{\s*:root\s*\{([\s\S]*?)\n  \}/);
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
const ARMS = ["--arm-naive", "--arm-rag", "--arm-system"];

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
    // The --arm-* values are a closed decision and are not re-chosen here: what this
    // checks is that the NEW primary does not drift towards them. The floor differs per
    // arm, and the difference is reasoned rather than an exemption to make the check pass:
    //   - arm-system is blue, the same family as --primary, and the only real confusion.
    //     Floor 15, the one a categorical scale gets.
    //   - arm-naive (plum) and arm-rag (green) are not confusable with the primary except
    //     under protanopia, where the plum loses its red and turns bluish. That is the same
    //     limitation CLAUDE.md already records as closed for the arms themselves ("they
    //     fail an all-pairs test, blue against plum, protanopic"), and the rule that
    //     compensates for it does not change either: the arms are always labelled, bars and
    //     rows only, never a scatter. Floor 10.
    for (const arm of ARMS) {
      if (!tokens[arm] || !tokens["--primary"]) continue;
      const floor = arm === "--arm-system" ? DE_MIN : 10;
      const d = deltaE(tokens["--primary"], tokens[arm], kind);
      const line = `ΔE ${kind.padEnd(6)} primary vs ${arm.slice(2)}: ${d.toFixed(1)} (mín ${floor})`;
      d >= floor ? ok(line) : fail(`${line}`);
    }
    // Y que los tres arcos sigan separados entre pares ADYACENTES en el orden declarado.
    for (let i = 0; i + 1 < ARMS.length; i++) {
      if (!tokens[ARMS[i]] || !tokens[ARMS[i + 1]]) continue;
      const d = deltaE(tokens[ARMS[i]], tokens[ARMS[i + 1]], kind);
      const line = `ΔE ${kind.padEnd(6)} ${ARMS[i].slice(2)} vs ${ARMS[i + 1].slice(2)}: ${d.toFixed(1)}`;
      d >= 9 ? ok(line) : fail(`${line} < 9`);
    }
  }
}

console.log(failures === 0 ? "\nTodo pasa.\n" : `\n${failures} comprobación(es) fallan.\n`);
process.exit(failures === 0 ? 0 : 1);
