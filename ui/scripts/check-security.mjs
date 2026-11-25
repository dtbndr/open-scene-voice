// Security gate (U16): scans ui/src for banned APIs and the build output for source maps and external references.
import { readdirSync, readFileSync, statSync, existsSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const uiRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const sourceRoot = join(uiRoot, 'src');
const buildRoot = resolve(uiRoot, '..', 'src', 'scenevoice', 'web', 'static');

const SOURCE_RULES = [
  ['localStorage', /localStorage/],
  ['sessionStorage', /sessionStorage/],
  ['indexedDB', /indexedDB/i],
  ['document.cookie', /document\.cookie/],
  ['location.search', /location\.search/],
  ['location.hash', /location\.hash/],
  ['URLSearchParams', /URLSearchParams/],
  ['the word token', /\btoken\b/i],
  ['console.', /\bconsole\./],
  ['{@html', /\{@html/],
  ['innerHTML', /innerHTML/],
  ['eval(', /\beval\s*\(/],
  ['new Function', /new\s+Function\b/]
];
const EXTERNAL = /(?:\bsrc\s*=|\bhref\s*=|url\(|@import)\s*["']?\s*(?:https?:)?\/\/(?!\/)/i;

function walk(dir) {
  const files = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) files.push(...walk(path));
    else files.push(path);
  }
  return files;
}

const problems = [];

for (const file of walk(sourceRoot)) {
  const lines = readFileSync(file, 'utf8').split('\n');
  lines.forEach((line, index) => {
    for (const [label, pattern] of SOURCE_RULES) {
      if (pattern.test(line)) problems.push(`${relative(uiRoot, file)}:${index + 1}: banned ${label}`);
    }
  });
}

if (!existsSync(buildRoot)) {
  problems.push(`build output missing: ${relative(uiRoot, buildRoot)} (run npm run build first)`);
} else {
  for (const file of walk(buildRoot)) {
    const shown = relative(uiRoot, file);
    if (file.endsWith('.map')) problems.push(`${shown}: source map file`);
    const text = readFileSync(file, 'utf8');
    if (text.includes('sourceMappingURL')) problems.push(`${shown}: sourceMappingURL`);
    if (/\.(html|css)$/.test(file) && EXTERNAL.test(text)) {
      problems.push(`${shown}: external reference (http://, https:// or // target)`);
    }
  }
}

if (problems.length) {
  console.error(`check:security failed (${problems.length}):\n${problems.join('\n')}`);
  process.exit(1);
}
console.log('check:security ok');
