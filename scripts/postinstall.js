'use strict';

const path        = require('path');
const fs          = require('fs');
const { spawnSync } = require('child_process');

if (process.platform !== 'win32') {
  // Nothing to do on non-Windows — app is Windows-only
  process.exit(0);
}

const PKG_ROOT  = path.join(__dirname, '..');
const VENV_DIR  = path.join(PKG_ROOT, '.venv');
const VENV_PY   = path.join(VENV_DIR, 'Scripts', 'python.exe');
const VENV_PIP  = path.join(VENV_DIR, 'Scripts', 'pip.exe');
const REQ_FILE  = path.join(PKG_ROOT, 'requirements.txt');

// ── helpers ──────────────────────────────────────────────────────────────────

function hr()          { console.log('  ' + '─'.repeat(52)); }
function step(n, t, s) { console.log(`\n  [${n}/${t}]  ${s}`); }
function info(s)       { console.log(`          ${s}`); }

function run(args, opts) {
  info('> ' + args.join(' '));
  return spawnSync(args[0], args.slice(1), { stdio: 'inherit', shell: false, ...opts });
}

// ── main ─────────────────────────────────────────────────────────────────────

console.log('\n');
hr();
console.log('  Whisper STT  |  Python Environment Setup');
hr();

// 1 — locate Python
step(1, 3, 'Checking Python 3.8+...');
let pythonExe = null;
for (const cmd of ['python', 'python3']) {
  const r = spawnSync(cmd, ['--version'], { encoding: 'utf-8', shell: true });
  if (r.status === 0) {
    const ver = (r.stdout || r.stderr || '').trim();
    info(`Found: ${ver}`);
    pythonExe = cmd;
    break;
  }
}
if (!pythonExe) {
  console.error('\n  ERROR: Python 3.8+ is required but was not found.');
  console.error('  Download: https://python.org');
  console.error('  During install, check "Add Python to PATH".\n');
  process.exit(1);
}

// 2 — create venv
step(2, 3, 'Creating virtual environment...');
if (fs.existsSync(VENV_PY)) {
  info('Already exists — skipping.');
} else {
  const r = run([pythonExe, '-m', 'venv', VENV_DIR]);
  if (r.status !== 0) {
    console.error('\n  ERROR: Failed to create virtual environment.\n');
    process.exit(1);
  }
  info(`Created: ${VENV_DIR}`);
}

// 3 — install deps
step(3, 3, 'Installing Python dependencies (may take a few minutes)...');
run([VENV_PIP, 'install', '--upgrade', 'pip', '--quiet']);
const r = run([VENV_PIP, 'install', '-r', REQ_FILE]);
if (r.status !== 0) {
  console.error('\n  ERROR: Failed to install Python dependencies.\n');
  process.exit(1);
}

console.log('\n');
hr();
console.log('  Setup complete!  Open a new terminal and run:   whisper');
hr();
console.log('\n');
