/* ── main.js ── */

/* ══════════════════════════════════════════════════════
   BOOT — no login required to view main page
   User area and subscription area load only if logged in
══════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  bootPage();
});

function bootPage() {
  const user = getUser();
  if (user) {
    // logged in — show full page
    initUserArea();
    loadSubscriptions();
  } else {
    // not logged in — show guest state
    initGuestState();
  }
}

/* ══════════════════════════════════════════════════════
   TAB NAVIGATION
══════════════════════════════════════════════════════ */
function switchTab(name, btn) {
  document.querySelectorAll('.tab-section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  btn.classList.add('active');
}

/* ══════════════════════════════════════════════════════
   LOGOUT — clear session → redirect to login.html
══════════════════════════════════════════════════════ */
function logout() {
  const user = getUser();
  clearUser();
  if (user) {
    // was logged in — redirect to login
    window.location.href = 'login.html';
  } else {
    // already guest — just go to login
    window.location.href = 'login.html';
  }
}



/* ══════════════════════════════════════════════════════
   GUEST STATE — shown when not logged in
══════════════════════════════════════════════════════ */
function initGuestState() {
  document.getElementById('topUsername').textContent = 'Guest';
  document.getElementById('userAvatar').textContent       = '?';
  document.getElementById('userDisplayName').textContent  = 'Not logged in';
  document.getElementById('userDisplayEmail').textContent = 'Sign in to view your profile';
  document.getElementById('userDisplayStatus').innerHTML  = '';
  ['puUsername','puFullName','puEmail','puCreated','puLastLogin'].forEach(id => {
    document.getElementById(id).textContent = '—';
  });
  document.getElementById('puStatus').textContent = '—';

  // subscription area — show sign in prompt
  document.getElementById('subList').innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">🔒</div>
      <div class="empty-title">Sign in to see your subscriptions</div>
      <div class="empty-desc">
        <a href="login.html" style="color:var(--accent);text-decoration:none;font-weight:600;">Sign in</a>
        &nbsp;or&nbsp;
        <a href="register.html" style="color:var(--accent);text-decoration:none;font-weight:600;">Create an account</a>
      </div>
    </div>`;
}

/* ══════════════════════════════════════════════════════
   1. USER AREA
══════════════════════════════════════════════════════ */
function initUserArea() {
  const user = getUser();

  // topbar username
  document.getElementById('topUsername').textContent = user.username || user.full_name || '—';

  // avatar initial
  document.getElementById('userAvatar').textContent =
    (user.full_name || user.username || '?')[0].toUpperCase();

  // profile header
  document.getElementById('userDisplayName').textContent  = user.full_name || user.username || '—';
  document.getElementById('userDisplayEmail').textContent = user.email || '—';
  document.getElementById('userDisplayStatus').innerHTML  = user.is_active
    ? '<span class="badge on">● Active</span>'
    : '<span class="badge off">● Inactive</span>';

  // grid fields
  set('puUsername',  user.username);
  set('puFullName',  user.full_name);
  set('puEmail',     user.email);
  set('puCreated',   user.created_at);
  set('puLastLogin', user.last_login);
  document.getElementById('puStatus').innerHTML = user.is_active
    ? '<span class="badge on">● Active</span>'
    : '<span class="badge off">● Inactive</span>';
}

function set(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val || '—';
}

/* ══════════════════════════════════════════════════════
   2. SUBSCRIPTION AREA
   - Only show songs THIS user subscribed to
   - New users → empty state
   - DynamoDB table: UserSubscriptions
     PK = username  SK = title_album
══════════════════════════════════════════════════════ */
async function loadSubscriptions() {
  const user = getUser();
  const wrap = document.getElementById('subList');
  wrap.innerHTML = '<div class="loading">Loading…</div>';

  try {
    // GET — Query subscriptions for this user
    const { ok, data } = await apiFetch(
      `/subscriptions?username=${encodeURIComponent(user.username)}`
    );

    const subs = (ok && data.subscriptions) ? data.subscriptions : [];

    if (subs.length === 0) {
      // brand-new user or no subscriptions yet — show empty state
      wrap.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">🎵</div>
          <div class="empty-title">No subscriptions yet</div>
          <div class="empty-desc">
            Go to the <strong>Query</strong> tab to search for music
            and click <em>Subscribe</em> to add songs here.
          </div>
        </div>`;
      updateSubCount(0);
      return;
    }

    // render subscribed songs with artist image + Remove button
    wrap.innerHTML = '';
    subs.forEach(s => wrap.appendChild(buildMusicCard(s, 'remove')));
    updateSubCount(subs.length);

  } catch (e) {
    wrap.innerHTML = '<div class="empty-state"><div class="empty-icon">⚠️</div><div class="empty-title">Could not load subscriptions</div><div class="empty-desc">Check your API URL in config.js</div></div>';
  }
}

async function removeSong(username, title_album, songTitle) {
  if (!confirm(`Remove "${songTitle}" from your subscriptions?`)) return;

  try {
    // DELETE — remove subscription from DynamoDB
    const { ok } = await apiFetch(
      `/subscriptions/${encodeURIComponent(username)}/${encodeURIComponent(title_album)}`,
      { method: 'DELETE' }
    );
    if (!ok) return toast('Failed to remove. Please try again.', 'err');

    toast(`"${songTitle}" removed from subscriptions.`);
    loadSubscriptions();   // reload subscription list

    // refresh query results to re-enable Subscribe button
    refreshQuerySubscribeButtons(title_album, false);

  } catch (e) {
    toast('Remove failed.', 'err');
  }
}

/* ══════════════════════════════════════════════════════
   3. QUERY AREA
   - Requires at least 1 field filled
   - Multiple fields = AND logic (client-side filter)
   - Results show artist image from S3 + Subscribe button
   - Never shows full DB scan
══════════════════════════════════════════════════════ */
async function runQuery() {
  const title  = document.getElementById('qTitle').value.trim();
  const artist = document.getElementById('qArtist').value.trim();
  const album  = document.getElementById('qAlbum').value.trim();
  const year   = document.getElementById('qYear').value.trim();

  // at least one field required
  if (!title && !artist && !album && !year) {
    toast('Please fill in at least one search field.', 'err');
    return;
  }

  const btn = document.getElementById('queryBtn');
  btn.disabled = true;
  btn.textContent = 'Searching…';

  document.getElementById('queryResults').style.display = 'none';
  document.getElementById('queryEmpty').style.display   = 'none';

  // ── Decide which DynamoDB index to use ──
  // Priority: artist+year → LSI, album → GSI AlbumIndex,
  //           year → GSI YearIndex, artist → base table Query
  let endpoint   = '';
  let indexLabel = '';

  if (artist && year) {
    endpoint   = `/songs?artist=${encodeURIComponent(artist)}&year=${encodeURIComponent(year)}`;
    indexLabel = '⚡ LSI — ArtistYearIndex (artist + year)';
  } else if (album) {
    endpoint   = `/songs?album=${encodeURIComponent(album)}`;
    indexLabel = '⚡ GSI — AlbumIndex';
  } else if (year) {
    endpoint   = `/songs?year=${encodeURIComponent(year)}`;
    indexLabel = '⚡ GSI — YearIndex';
  } else if (artist) {
    endpoint   = `/songs?artist=${encodeURIComponent(artist)}`;
    indexLabel = '⚡ Query — base table (PK: artist)';
  } else if (title) {
    // title-only: use scan + client-side filter (no title index)
    endpoint   = `/songs`;
    indexLabel = '⚡ Scan + client-side title filter';
  }

  // show index label
  const tag = document.getElementById('queryIndexTag');
  tag.textContent = indexLabel;
  tag.classList.add('show');

  try {
    const { ok, data } = await apiFetch(endpoint);
    let songs = ok ? (data.songs || data.items || []) : [];

    // ── AND filter: apply all filled fields client-side ──
    songs = songs.filter(s => {
      const matchTitle  = !title  || s.title?.toLowerCase().includes(title.toLowerCase());
      const matchArtist = !artist || s.artist?.toLowerCase().includes(artist.toLowerCase());
      const matchAlbum  = !album  || s.album?.toLowerCase().includes(album.toLowerCase());
      const matchYear   = !year   || s.year === year;
      return matchTitle && matchArtist && matchAlbum && matchYear;
    });

    if (songs.length === 0) {
      document.getElementById('queryEmpty').style.display = 'block';
    } else {
      // get user's current subscriptions to mark already-subscribed songs
      const user = getUser();
      const { data: subData } = await apiFetch(
        `/subscriptions?username=${encodeURIComponent(user.username)}`
      ).catch(() => ({ data: {} }));
      const subSet = new Set(
        (subData.subscriptions || []).map(s => s.title_album)
      );

      const wrap = document.getElementById('queryResults');
      wrap.innerHTML = '';
      songs.forEach(s => {
        const isSubbed = subSet.has(s.title_album);
        wrap.appendChild(buildMusicCard(s, 'subscribe', isSubbed));
      });
      wrap.style.display = 'flex';
    }

  } catch (e) {
    toast('Query failed. Check config.js API URL.', 'err');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Query';
  }
}

function clearQuery() {
  ['qTitle','qArtist','qAlbum','qYear'].forEach(id => {
    document.getElementById(id).value = '';
  });
  document.getElementById('queryResults').style.display = 'none';
  document.getElementById('queryEmpty').style.display   = 'none';
  const tag = document.getElementById('queryIndexTag');
  tag.classList.remove('show');
  tag.textContent = '';
}

async function subscribeSong(song, btn) {
  const user = getUser();

  btn.disabled    = true;
  btn.textContent = 'Subscribing…';

  try {
    // POST — save subscription to DynamoDB UserSubscriptions table
    const { ok, data } = await apiFetch('/subscriptions', {
      method: 'POST',
      body: JSON.stringify({
        username:    user.username,
        title_album: song.title_album,
        title:       song.title,
        artist:      song.artist,
        album:       song.album,
        year:        song.year   || '',
        img_url:     song.img_url || '',
      }),
    });

    if (!ok) {
      toast(data.error || 'Subscribe failed.', 'err');
      btn.disabled = false;
      btn.textContent = 'Subscribe';
      return;
    }

    // update button to show already subscribed
    btn.textContent = '✓ Subscribed';
    btn.classList.add('subscribed');
    toast(`"${song.title}" added to your subscriptions!`);

    // refresh subscription tab count
    loadSubscriptions();

  } catch (e) {
    toast('Subscribe failed.', 'err');
    btn.disabled = false;
    btn.textContent = 'Subscribe';
  }
}

/* ══════════════════════════════════════════════════════
   HELPER — build a music card DOM element
   mode: 'subscribe' (query results) | 'remove' (subscription list)
══════════════════════════════════════════════════════ */
function buildMusicCard(song, mode, alreadySubscribed = false) {
  const card = document.createElement('div');
  card.className = 'music-card';
  card.dataset.titleAlbum = song.title_album;

  // artist image from S3
  const imgWrap = document.createElement('div');
  if (song.img_url) {
    const img = document.createElement('img');
    img.className = 'music-img';
    img.src = song.img_url;
    img.alt = song.artist;
    img.onerror = () => {
      img.replaceWith(placeholder());
    };
    imgWrap.appendChild(img);
  } else {
    imgWrap.appendChild(placeholder());
  }
  card.appendChild(imgWrap);

  // song info
  const info = document.createElement('div');
  info.className = 'music-info';
  info.innerHTML = `
    <div class="music-title">${esc(song.title)}</div>
    <div class="music-artist">${esc(song.artist)}</div>
    <div class="music-meta">${esc(song.album)}${song.year ? ' · ' + esc(song.year) : ''}</div>`;
  card.appendChild(info);

  // action button
  const actionWrap = document.createElement('div');
  actionWrap.className = 'music-action';

  if (mode === 'remove') {
    const btn = document.createElement('button');
    btn.className = 'btn-remove';
    btn.textContent = 'Remove';
    btn.onclick = () => removeSong(getUser().username, song.title_album, song.title);
    actionWrap.appendChild(btn);

  } else {
    const btn = document.createElement('button');
    btn.className = 'btn-subscribe' + (alreadySubscribed ? ' subscribed' : '');
    btn.textContent = alreadySubscribed ? '✓ Subscribed' : 'Subscribe';
    if (alreadySubscribed) {
      btn.disabled = true;
    } else {
      btn.onclick = () => subscribeSong(song, btn);
    }
    actionWrap.appendChild(btn);
  }

  card.appendChild(actionWrap);
  return card;
}

function placeholder() {
  const div = document.createElement('div');
  div.className = 'music-img-placeholder';
  div.textContent = '🎵';
  return div;
}

/* refresh Subscribe buttons in query results after a remove */
function refreshQuerySubscribeButtons(title_album, subscribed) {
  document.querySelectorAll(`.music-card[data-title-album="${CSS.escape(title_album)}"]`).forEach(card => {
    const btn = card.querySelector('.btn-subscribe');
    if (!btn) return;
    if (!subscribed) {
      btn.disabled = false;
      btn.textContent = 'Subscribe';
      btn.classList.remove('subscribed');
    }
  });
}

/* update the count badge on the Subscription tab */
function updateSubCount(n) {
  const btn = document.querySelector('.tab-btn:nth-child(2)');
  const existing = btn.querySelector('.sub-count');
  if (existing) existing.remove();
  if (n > 0) {
    const badge = document.createElement('span');
    badge.className = 'sub-count';
    badge.textContent = n;
    btn.appendChild(badge);
  }
}