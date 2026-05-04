const DEFAULT_SETTINGS = {
  apiBase: 'http://localhost:9876',
  outputDir: '',
  format: 'mp4',
  quality: '720',
  autoLoadInfo: true,
  textSize: 'normal'
};

let currentUrl = '';
let selectedFormat = 'mp4';
let selectedQuality = '720';
let serverOnline = false;
let settings = { ...DEFAULT_SETTINGS };
let currentInfo = null;

const urlInput = document.getElementById('url-input');
const loadBtn  = document.getElementById('load-btn');
const dlBtn    = document.getElementById('dl-btn');
const logBox   = document.getElementById('log-box');
const srvWarn  = document.getElementById('srv-warn');
const srvDot   = document.getElementById('srv-dot');
const srvLabel = document.getElementById('srv-label');
const srvPill  = document.getElementById('srv-pill');
const settingsBtn = document.getElementById('settings-btn');
const videoInfo = document.getElementById('video-info');
const qSection  = document.getElementById('q-section');
const apiUrlLabel = document.getElementById('api-url-label');
const metaTitle = document.getElementById('meta-title');
const metaArtist = document.getElementById('meta-artist');
const metaAlbum = document.getElementById('meta-album');
const metaGenre = document.getElementById('meta-genre');
const metaDate = document.getElementById('meta-date');
const metaComment = document.getElementById('meta-comment');

// ── Init ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  settings = await loadSettings();
  applySettings(settings);
  await checkServer();

  // Auto-fill current YouTube tab URL
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.url && isYtUrl(tab.url)) {
      urlInput.value = tab.url;
      currentUrl = tab.url;
      if (serverOnline && settings.autoLoadInfo) await loadInfo(tab.url);
    }
  } catch (_) {}
});

// ── Server check ──────────────────────────────────────
async function checkServer() {
  try {
    const r = await fetch(`${settings.apiBase}/ping`, { signal: AbortSignal.timeout(2000) });
    const d = await r.json();
    serverOnline = true;
    srvDot.classList.add('on');
    srvLabel.textContent = `v${d.version || 'OK'}`;
    srvWarn.classList.remove('show');
    log(`✔ サーバー接続OK  yt-dlp ${d.version}`, 'ok');
  } catch {
    serverOnline = false;
    srvDot.classList.remove('on');
    srvLabel.textContent = 'オフライン';
    srvWarn.classList.add('show');
    log(`✘ サーバーに接続できません (${settings.apiBase})`, 'err');
  }
}

srvPill.addEventListener('click', () => checkServer());
settingsBtn.addEventListener('click', () => chrome.runtime.openOptionsPage());

// ── Format ────────────────────────────────────────────
document.querySelectorAll('.fmt-btn').forEach(b => {
  b.addEventListener('click', () => {
    document.querySelectorAll('.fmt-btn').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    selectedFormat = b.dataset.f;
    qSection.style.display = ['mp3','m4a'].includes(selectedFormat) ? 'none' : 'block';
  });
});

// ── Quality ───────────────────────────────────────────
document.querySelectorAll('.q-chip').forEach(c => {
  c.addEventListener('click', () => {
    document.querySelectorAll('.q-chip').forEach(x => x.classList.remove('active'));
    c.classList.add('active');
    selectedQuality = c.dataset.q;
  });
});

// ── Load info ─────────────────────────────────────────
loadBtn.addEventListener('click', async () => {
  const url = urlInput.value.trim();
  if (!url) { log('URLを入力してください', 'err'); return; }
  if (!isYtUrl(url)) { log('YouTube URLを入力してください', 'err'); return; }
  if (!serverOnline) { log('サーバーが起動していません', 'err'); await checkServer(); return; }
  currentUrl = url;
  await loadInfo(url);
});

urlInput.addEventListener('keydown', e => { if (e.key === 'Enter') loadBtn.click(); });

async function loadInfo(url) {
  loadBtn.disabled = true;
  dlBtn.disabled = true;
  videoInfo.classList.remove('show');
  currentInfo = null;
  log('⟳ 動画情報を取得中...', 'info');

  try {
    const r = await fetch(`${settings.apiBase}/info?url=${encodeURIComponent(url)}`, {
      signal: AbortSignal.timeout(30000)
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const d = await r.json();
    if (d.error) throw new Error(d.error);

    // Display card
    document.getElementById('thumb').src = d.thumbnail || '';
    document.getElementById('vtitle').textContent = d.title || '—';
    document.getElementById('vch').textContent = `📺 ${d.uploader || '—'}`;
    document.getElementById('vviews').textContent = d.view_count
      ? `👁 ${Number(d.view_count).toLocaleString()}`
      : '';
    document.getElementById('dur').textContent = fmtDur(d.duration || 0);
    currentInfo = d;
    applyInfoToMetadata(d);

    videoInfo.classList.add('show');
    dlBtn.disabled = false;
    log(`✔ "${d.title}"`, 'ok');
  } catch (e) {
    log(`✘ 情報取得失敗: ${e.message}`, 'err');
  }
  loadBtn.disabled = false;
}

// ── Download ──────────────────────────────────────────
dlBtn.addEventListener('click', async () => {
  if (!currentUrl) return;
  if (!serverOnline) { await checkServer(); return; }

  dlBtn.disabled = true;
  dlBtn.innerHTML = '<span class="spin"></span> 送信中...';

  const outputDir = settings.outputDir.trim();

  try {
    const r = await fetch(`${settings.apiBase}/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: currentUrl,
        format: selectedFormat,
        quality: selectedQuality,
        outputDir: outputDir || undefined,
        metadata: readMetadata()
      }),
      signal: AbortSignal.timeout(10000)
    });
    const d = await r.json();
    if (d.error) throw new Error(d.error);

    log(`✔ ダウンロード開始！`, 'ok');
    log(`📁 保存先: ${d.outputDir}`, 'info');
    log('   ターミナルで進捗を確認してください', 'info');
  } catch (e) {
    log(`✘ エラー: ${e.message}`, 'err');
  }

  dlBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg> ダウンロード開始`;
  dlBtn.disabled = false;
});

// ── Helpers ───────────────────────────────────────────
async function loadSettings() {
  return new Promise(resolve => {
    chrome.storage.sync.get(DEFAULT_SETTINGS, saved => {
      resolve({
        ...DEFAULT_SETTINGS,
        ...saved,
        apiBase: normalizeApiBase(saved.apiBase || DEFAULT_SETTINGS.apiBase)
      });
    });
  });
}

function applySettings(nextSettings) {
  selectedFormat = nextSettings.format;
  selectedQuality = nextSettings.quality;
  apiUrlLabel.textContent = nextSettings.apiBase;
  document.body.classList.toggle('large-text', nextSettings.textSize === 'large');
  setActiveByData('.fmt-btn', 'f', selectedFormat);
  setActiveByData('.q-chip', 'q', selectedQuality);
  qSection.style.display = ['mp3','m4a'].includes(selectedFormat) ? 'none' : 'block';
}

function setActiveByData(selector, key, value) {
  document.querySelectorAll(selector).forEach(el => {
    el.classList.toggle('active', el.dataset[key] === value);
  });
}

function normalizeApiBase(value) {
  return String(value || DEFAULT_SETTINGS.apiBase).replace(/\/+$/, '');
}

function applyInfoToMetadata(info) {
  metaTitle.value = info.title || '';
  metaArtist.value = firstText(info.artist, info.artists, info.creator, info.creators, info.uploader);
  metaAlbum.value = '';
  metaGenre.value = '';
  metaDate.value = formatUploadDate(info.upload_date || '');
  metaComment.value = info.description || '';
}

function readMetadata() {
  return {
    title: metaTitle.value.trim(),
    artist: metaArtist.value.trim(),
    album: metaAlbum.value.trim(),
    genre: metaGenre.value.trim(),
    date: metaDate.value.trim(),
    comment: metaComment.value.trim()
  };
}

function formatUploadDate(value) {
  if (!/^\d{8}$/.test(value)) return '';
  return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6)}`;
}

function firstText(...values) {
  for (const value of values) {
    if (Array.isArray(value) && value.length) {
      const text = value.filter(isUsefulMetadataText).join(', ');
      if (text) return text;
    }
    if (isUsefulMetadataText(value)) return value.trim();
  }
  return '';
}

function isUsefulMetadataText(value) {
  if (typeof value !== 'string') return false;
  const text = value.trim();
  return text && !['na', 'n/a', 'none', 'unknown', 'null', '-'].includes(text.toLowerCase());
}

function isYtUrl(url) {
  try {
    const u = new URL(url);
    return (u.hostname.endsWith('youtube.com') && u.searchParams.has('v'))
        || u.hostname === 'youtu.be';
  } catch { return false; }
}

function fmtDur(sec) {
  if (!sec) return '';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  return `${m}:${String(s).padStart(2,'0')}`;
}

function log(msg, type = '') {
  logBox.classList.add('show');
  const span = document.createElement('div');
  span.textContent = msg;
  if (type === 'ok')   span.className = 'log-ok';
  if (type === 'err')  span.className = 'log-err';
  if (type === 'info') span.className = 'log-info';
  logBox.appendChild(span);
  logBox.scrollTop = logBox.scrollHeight;
}
