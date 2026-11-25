// Build-time guide generator: turns docs/script-format.md (the repo's one script guide) into ui/static/guide.json.
// Dependency-free. The output is data only (headings, paragraphs, bullets, code); the page renders it as text.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const uiRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = join(uiRoot, '..', 'docs', 'script-format.md');
const target = join(uiRoot, 'static', 'guide.json');

/** Split one line of text into plain and `code` parts. */
function inline(text) {
  const parts = [];
  text.split(/(`[^`]+`)/).forEach((piece) => {
    if (piece === '') return;
    if (piece.length > 2 && piece.startsWith('`') && piece.endsWith('`')) parts.push({ text: piece.slice(1, -1), code: true });
    else parts.push({ text: piece });
  });
  return parts;
}

function parseGuide(markdown) {
  const blocks = [];
  let paragraph = [];
  let list = null;
  let fence = null;
  const flush = () => {
    if (paragraph.length) blocks.push({ kind: 'paragraph', parts: inline(paragraph.join(' ')) });
    if (list) blocks.push({ kind: 'list', items: list.map((item) => inline(item)) });
    paragraph = [];
    list = null;
  };
  for (const line of markdown.replace(/\r\n?/g, '\n').split('\n')) {
    if (fence !== null) {
      if (line.startsWith('```')) {
        blocks.push({ kind: 'code', text: fence.join('\n') });
        fence = null;
      } else fence.push(line);
      continue;
    }
    if (line.startsWith('```')) {
      flush();
      fence = []; // the info string (such as script-valid) is a test tag, not shown
      continue;
    }
    const heading = /^(#{1,6}) (.*)$/.exec(line);
    if (heading) {
      flush();
      blocks.push({ kind: 'heading', level: heading[1].length, text: heading[2].trim() });
    } else if (/^[-*] /.test(line)) {
      if (paragraph.length) flush();
      (list ??= []).push(line.slice(2).trim());
    } else if (line.trim() === '') {
      flush();
    } else if (list && /^\s+\S/.test(line)) {
      list[list.length - 1] += ` ${line.trim()}`;
    } else {
      if (list) flush();
      paragraph.push(line.trim());
    }
  }
  if (fence !== null) blocks.push({ kind: 'code', text: fence.join('\n') });
  flush();
  return { blocks };
}

mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, `${JSON.stringify(parseGuide(readFileSync(source, 'utf8')))}\n`);
