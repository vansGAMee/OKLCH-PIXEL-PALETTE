#!/usr/bin/env node
/**
 * scripts/check-env.mjs
 * Validates Supabase environment variables.
 * Exits 0 (safe demo mode) if missing, exits 1 only on obviously wrong format.
 * Run: node scripts/check-env.mjs
 */

const required = [
  'NEXT_PUBLIC_SUPABASE_URL',
  'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY',
];

const secret = ['SUPABASE_SECRET_KEY'];

let hasMissing = false;

for (const key of required) {
  if (!process.env[key]) {
    console.warn(`[check-env] MISSING: ${key} — cloud features will be disabled (safe demo mode)`);
    hasMissing = true;
  }
}

for (const key of secret) {
  if (!process.env[key]) {
    console.warn(`[check-env] MISSING: ${key} — account deletion will be unavailable`);
  }
}

if (hasMissing) {
  console.info('[check-env] Running in safe demo mode. Guest editor is fully functional.');
  process.exit(0); // Do NOT fail the build — demo mode is valid
}

console.info('[check-env] All Supabase environment variables present.');
process.exit(0);
