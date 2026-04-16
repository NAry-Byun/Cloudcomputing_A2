/* ── register.js ── */

document.addEventListener('DOMContentLoaded', () => {
  if (getUser()) window.location.href = 'main.html';

  // live password strength check
  document.getElementById('regPassword')
    .addEventListener('input', e => checkStrength(e.target.value));
});

/* ── password strength checker ── */
function checkStrength(pw) {
  const len   = pw.length >= 6;
  const num   = /\d/.test(pw);
  const upper = /[A-Z]/.test(pw);

  toggleReq('req-len',   len);
  toggleReq('req-num',   num);
  toggleReq('req-upper', upper);

  const score  = [len, num, upper].filter(Boolean).length;
  const colors = ['', '#ff6b6b', '#f0a500', '#6bffb8'];
  const labels = ['', 'Weak', 'Fair', 'Strong'];

  const bar  = document.getElementById('strengthBar');
  const text = document.getElementById('strengthText');

  bar.style.width      = score * 33.3 + '%';
  bar.style.background = colors[score];
  text.textContent     = score > 0 ? labels[score] : '';
  text.style.color     = colors[score];
}

function toggleReq(id, met) {
  document.getElementById(id).classList.toggle('met', met);
}

/* ── registration handler ── */
async function handleRegister() {
  const username = document.getElementById('regUsername').value.trim();
  const fullName = document.getElementById('regFullName').value.trim();
  const email    = document.getElementById('regEmail').value.trim();
  const password = document.getElementById('regPassword').value;
  const confirm  = document.getElementById('regConfirm').value;

  clearMsg('msg');

  // validation
  if (!username || !email || !password || !confirm)
    return showMsg('msg', 'Please fill in all fields.', 'error');

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
    return showMsg('msg', 'Please enter a valid email address.', 'error');

  if (password.length < 6)
    return showMsg('msg', 'Password must be at least 6 characters.', 'error');

  if (password !== confirm)
    return showMsg('msg', 'Passwords do not match.', 'error');

  const btn = document.getElementById('regBtn');
  btn.disabled    = true;
  btn.textContent = 'Creating account…';

  try {
    const today = new Date().toISOString().split('T')[0];

    // POST — create user in DynamoDB Users table
    const { ok, data } = await apiFetch('/users', {
      method: 'POST',
      body: JSON.stringify({
        username,
        email,
        password_hash: password,
        full_name:     fullName || username,
        created_at:    today,
        last_login:    today,
        is_active:     true,
      }),
    });

    if (!ok) {
      showMsg('msg', data.error || 'Registration failed. Username may already exist.', 'error');
      return;
    }

    showMsg('msg', 'Account created! Redirecting to login…', 'success');
    setTimeout(() => { window.location.href = 'login.html'; }, 1500);

  } catch (e) {
    showMsg('msg', 'Registration failed. Check your API URL in config.js.', 'error');
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Create Account';
  }
}