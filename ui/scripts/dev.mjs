// Dev loop (U4): build, stop the server this script started before, start a fresh one, print its launch link.
// Default: scripts/dev_web_server.py (real routes; `keys`, `plan` and `pack` on the real CLI, paid verbs on a stub, so no
// provider can be reached). `--real` runs the real CLI instead; `--keep-keys` keeps the scratch key file.
import { spawn, spawnSync } from 'node:child_process';
import { closeSync, existsSync, mkdirSync, openSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const uiRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const repo = resolve(uiRoot, '..');
const devDir = join(uiRoot, '.dev');
const workspace = join(devDir, 'workspace');
const keysFile = join(devDir, 'keys.env');
const pidFile = join(devDir, 'server.pid');
const logFile = join(devDir, 'server.log');
const scenarioFile = join(devDir, 'beats-scenario.txt');
const synthScenarioFile = join(devDir, 'synth-scenario.txt');
const alignScenarioFile = join(devDir, 'align-scenario.txt');
const python = join(repo, '.venv', 'bin', 'python');
const PORT = '47615';
const args = new Set(process.argv.slice(2));
const real = args.has('--real');
const keepKeys = args.has('--keep-keys');

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
const alive = (pid) => {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
};

async function stopPrevious() {
  if (!existsSync(pidFile)) return;
  const pid = Number(readFileSync(pidFile, 'utf8').trim());
  rmSync(pidFile, { force: true });
  if (!Number.isInteger(pid) || pid <= 1 || !alive(pid)) return;
  // Guard against a reused pid: only signal a process that looks like ours.
  const command = spawnSync('ps', ['-p', String(pid), '-o', 'command='], { encoding: 'utf8' }).stdout;
  if (!/dev_web_server\.py|scenevoice/.test(command)) return;
  process.kill(pid, 'SIGINT');
  for (let waited = 0; alive(pid) && waited < 15000; waited += 100) await sleep(100);
  if (alive(pid)) throw new Error(`previous server (pid ${pid}) did not stop after SIGINT; stop it by hand`);
}

const build = spawnSync('npm', ['run', 'build'], { cwd: uiRoot, stdio: 'inherit' });
if (build.status !== 0) process.exit(build.status ?? 1);

await stopPrevious();
mkdirSync(workspace, { recursive: true });
if (!keepKeys) rmSync(keysFile, { force: true });

const command = real
  ? [python, '-m', 'scenevoice', 'web', '--no-open', '--port', PORT]
  : [python, join(repo, 'scripts', 'dev_web_server.py'), '--port', PORT, '--workspace', workspace, '--keys-file', keysFile, '--beats-scenario', scenarioFile, '--synth-scenario', synthScenarioFile, '--align-scenario', alignScenarioFile];
if (real) {
  console.warn('WARNING: --real runs the real CLI. Valid keys saved in the scratch key file CAN spend quota.');
}
writeFileSync(logFile, '');
const log = openSync(logFile, 'a');
const child = spawn(command[0], command.slice(1), {
  cwd: repo,
  detached: true,
  stdio: ['ignore', log, log],
  env: { ...process.env, SCENEVOICE_WORKSPACE: workspace, SCENEVOICE_KEYS_FILE: keysFile }
});
closeSync(log);
child.unref();
writeFileSync(pidFile, String(child.pid));

let link = null;
for (let waited = 0; waited < 20000 && !link; waited += 100) {
  const match = readFileSync(logFile, 'utf8').match(/http:\/\/127\.0\.0\.1:\d+\/\?token=\S+/);
  if (match) link = match[0];
  else if (!alive(child.pid)) break;
  else await sleep(100);
}
if (!link) {
  console.error(`server did not print a link; see ${logFile}:\n${readFileSync(logFile, 'utf8')}`);
  process.exit(1);
}
console.log(link);
