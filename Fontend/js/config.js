/* ── config.js — shared API URL and utilities ── */

const API_URL = "https://rj556c0qb9.execute-api.us-east-1.amazonaws.com/musicapi";

/* ── Auth helpers ── */
function getUser() {
  const raw = sessionStorage.getItem('user');
  return raw ? JSON.parse(raw) : null;
}

function requireAuth() {
  if (!getUser()) window.location.href = 'login.html';
}

function saveUser(user) {
  sessionStorage.setItem('user', JSON.stringify(user));
}

function clearUser() {
  sessionStorage.removeItem('user');
}

/* ── Toast notification ── */
function toast(msg, type = 'ok') {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.className = 'toast ' + type;
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.className = 'toast'; }, 3000);
}

/* ── Message box helper ── */
function showMsg(id, text, type) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className = 'msg ' + type;
}

function clearMsg(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = 'msg';
}

/* ── Escape HTML ── */
function esc(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ── API fetch wrapper ── */
async function apiFetch(path, options = {}) {
  const res = await fetch(API_URL + path, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}