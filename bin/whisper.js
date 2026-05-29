#!/usr/bin/env node
'use strict';

const path        = require('path');
const fs          = require('fs');
const { spawnSync } = require('child_process');

if (process.platform !== 'win32') {
  console.error('\n  Whisper STT is Windows-only.\n');
  process.exit(1);
}

const PKG_ROOT    = path.join(__dirname, '..');
const VENV_PY     = path.join(PKG_ROOT, '.venv', 'Scripts', 'python.exe');
const SETUP_JS    = path.join(PKG_ROOT, 'scripts', 'postinstall.js');

// First-run guard: postinstall should have run, but just in case
if (!fs.existsSync(VENV_PY)) {
  console.log('\n  First run — setting up Python environment...\n');
  const r = spawnSync(process.execPath, [SETUP_JS], { stdio: 'inherit' });
  if (r.status !== 0) {
    console.error('\n  Setup failed. Try reinstalling:');
    console.error('    npm i -g github:Iam-Divyesh/whisper\n');
    process.exit(1);
  }
}

// Launch interactive settings UI
const result = spawnSync(
  VENV_PY,
  ['-m', 'whisper_stt.cli.settings_ui'],
  {
    stdio: 'inherit',
    cwd: PKG_ROOT,
    env: { ...process.env, PYTHONPATH: PKG_ROOT },
  }
);

process.exit(result.status || 0);
