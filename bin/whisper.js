#!/usr/bin/env node
'use strict';

const path        = require('path');
const fs          = require('fs');
const { spawnSync } = require('child_process');

if (process.platform !== 'win32') {
  console.error('\n  Whisper STT is Windows-only.\n');
  process.exit(1);
}

const PKG_ROOT = path.join(__dirname, '..');
const VENV_PY  = path.join(PKG_ROOT, '.venv', 'Scripts', 'python.exe');
const SETUP_JS = path.join(PKG_ROOT, 'scripts', 'postinstall.js');

// Run setup on first use (postinstall can't do this reliably because npm
// runs it from a temp clone dir before moving the package to node_modules)
if (!fs.existsSync(VENV_PY)) {
  console.log('\n  First run — setting up Python environment...');
  console.log('  This takes a few minutes. Only happens once.\n');
  const r = spawnSync(process.execPath, [SETUP_JS], { stdio: 'inherit' });
  if (r.status !== 0) {
    console.error('\n  Setup failed. Make sure Python 3.8+ is installed:');
    console.error('  https://python.org  (check "Add Python to PATH")\n');
    process.exit(1);
  }
}

// Launch interactive settings UI
const result = spawnSync(
  VENV_PY,
  ['-m', 'whisper_stt.cli.settings_ui'],
  {
    stdio: 'inherit',
    cwd:   PKG_ROOT,
    env:   { ...process.env, PYTHONPATH: PKG_ROOT },
  }
);

process.exit(result.status || 0);
