/* ── login.js ── */

document.addEventListener('DOMContentLoaded', () => {
  // redirect if already logged in
  if (getUser()) window.location.href = 'index.html';

  // allow Enter key on password field
  document.getElementById('loginPassword')
    .addEventListener('keydown', e => {
      if (e.key === 'Enter') handleLogin();
    });
});

async function handleLogin() {
  const email    = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;

  clearMsg('msg');

  if (!email || !password) {
    return showMsg('msg', 'Please fill in all fields.', 'error');
  }

  const btn = document.getElementById('loginBtn');
  btn.disabled = true;
  btn.textContent = 'Signing in…';

  try {
    // GET — Query GSI EmailIndex to find user by email
    const { ok, data } = await apiFetch(
      `/users/by-email?email=${encodeURIComponent(email)}`
    );

    if (!ok) {
      showMsg('msg', 'No account found with that email.', 'error');
      return;
    }

    if (data.password_hash !== password) {
      showMsg('msg', 'Incorrect password.', 'error');
      return;
    }

    // save to session and go to main
    saveUser(data);
    showMsg('msg', `Welcome back, ${data.full_name || data.username}!`, 'success');
    setTimeout(() => { window.location.href = 'index.html'; }, 800);

  } catch (e) {
    showMsg('msg', 'Login failed. Check your API URL in config.js.', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Sign In';
  }
}