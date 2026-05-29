'use strict';

const path = require('path');
const fs   = require('fs');
const { spawn, spawnSync } = require('child_process');

if (process.platform !== 'win32') { process.exit(0); }

const PKG_ROOT = path.join(__dirname, '..');
const VENV_DIR = path.join(PKG_ROOT, '.venv');
const VENV_PY  = path.join(VENV_DIR, 'Scripts', 'python.exe');
const VENV_PIP = path.join(VENV_DIR, 'Scripts', 'pip.exe');
const REQ_FILE = path.join(PKG_ROOT, 'requirements.txt');

// ── Box UI ───────────────────────────────────────────────────────────────────

const W     = 54;
const out   = s => process.stdout.write(s);
const top   = () => out(`  ┌${'─'.repeat(W)}┐\n`);
const bot   = () => out(`  └${'─'.repeat(W)}┘\n`);
const sep   = () => out(`  ├${'─'.repeat(W)}┤\n`);
const row   = (t = '') => out(`  │ ${String(t).padEnd(W - 2)} │\n`);

// ── Spinner ───────────────────────────────────────────────────────────────────

const FRAMES = ['-', '\\', '|', '/'];

function runWithSpinner(label, cmd, args) {
  return new Promise(resolve => {
    let fi = 0;
    const tick = () => out(`\r  │ [${FRAMES[fi++ % 4]}] ${label.padEnd(W - 6)} │`);
    tick();
    const timer = setInterval(tick, 120);

    const child = spawn(cmd, args, { stdio: ['ignore', 'pipe', 'pipe'] });
    let stderr = '';
    child.stderr.on('data', d => { stderr += d.toString(); });

    child.on('close', code => {
      clearInterval(timer);
      const icon = code === 0 ? '✓' : '✗';
      out(`\r  │ [${icon}] ${label.padEnd(W - 6)} │\n`);
      resolve({ code, stderr });
    });
  });
}

// ── Main ─────────────────────────────────────────────────────────────────────

async function main() {
  out('\n');
  top();
  row();
  row('  WHISPER STT  |  Setting up...');
  row();
  sep();
  row();

  // ── 1. Find Python ──────────────────────────────────────────────────────────
  let pythonExe = null;
  out(`  │ [-] Checking Python 3.8+...${' '.repeat(W - 29)} │`);

  for (const cmd of ['python', 'python3']) {
    const r = spawnSync(cmd, ['--version'], { encoding: 'utf-8', shell: true });
    if (r.status === 0) {
      const ver = (r.stdout || r.stderr || '').trim();
      out(`\r  │ [✓] ${ver.padEnd(W - 6)} │\n`);
      pythonExe = cmd;
      break;
    }
  }

  if (!pythonExe) {
    out(`\r  │ [✗] Python not found!${' '.repeat(W - 23)} │\n`);
    row();
    row('  Install Python 3.8+ from:  https://python.org');
    row('  During install, tick "Add Python to PATH".');
    row();
    bot();
    process.exit(1);
  }

  // ── 2. Create venv ─────────────────────────────────────────────────────────
  if (fs.existsSync(VENV_PY)) {
    row('[✓] Virtual environment already exists.');
  } else {
    out(`  │ [-] Creating virtual environment...${' '.repeat(W - 37)} │`);
    const r = spawnSync(pythonExe, ['-m', 'venv', VENV_DIR], {
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    if (r.status !== 0) {
      out(`\r  │ [✗] Failed to create virtual environment.${' '.repeat(W - 43)} │\n`);
      row();
      bot();
      process.exit(1);
    }
    out(`\r  │ [✓] Virtual environment created.${' '.repeat(W - 34)} │\n`);
  }

  // ── 3. Install Python dependencies ─────────────────────────────────────────
  row();
  row('  Downloading Python packages...');
  row('  (takes a few minutes on first install)');
  row();

  const r1 = await runWithSpinner(
    'Upgrading pip',
    VENV_PIP, ['install', '--upgrade', 'pip', '--quiet']
  );
  if (r1.code !== 0) { row('[✗] pip upgrade failed — continuing...'); }

  const r2 = await runWithSpinner(
    'Installing faster-whisper + dependencies',
    VENV_PIP, ['install', '-r', REQ_FILE, '--quiet']
  );

  if (r2.code !== 0) {
    row();
    row('[✗] Installation failed.');
    row('    Run this manually to see the full error:');
    row(`    ${VENV_PIP} install -r ${REQ_FILE}`);
    row();
    bot();
    process.exit(1);
  }

  // ── Done ───────────────────────────────────────────────────────────────────
  row();
  sep();
  row();
  row('  [✓] Setup complete!');
  row();
  row('  Open a new terminal and run:   whisper');
  row();
  bot();
  out('\n');
}

main().catch(e => { console.error(e); process.exit(1); });
