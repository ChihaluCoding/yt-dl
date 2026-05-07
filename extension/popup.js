const DEFAULT_SETTINGS = {
  apiBase: 'http://localhost:9876',
  format: 'mp4',
  quality: '720',
  autoLoadInfo: true,
  showLog: true,
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
const apiUrlLabel = document.getElementById('api-url-label');
const formatSelect = document.getElementById('format-select');
const qualitySelect = document.getElementById('quality-select');

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

formatSelect.addEventListener('change', () => {
  selectedFormat = formatSelect.value;
  updateQualityState();
});

qualitySelect.addEventListener('change', () => {
  selectedQuality = qualitySelect.value;
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
      signal: AbortSignal.timeout(70000)
    });
    const d = await readJsonResponse(r);
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

    videoInfo.classList.add('show');
    dlBtn.disabled = false;
    log(`✔ "${d.title}"`, 'ok');
  } catch (e) {
    log(`✘ 情報取得失敗: ${formatYtdlpError(e.message)}`, 'err');
  }
  loadBtn.disabled = false;
}

// ── Download ──────────────────────────────────────────
dlBtn.addEventListener('click', async () => {
  if (!currentUrl) return;
  if (!serverOnline) { await checkServer(); return; }

  dlBtn.disabled = true;
  dlBtn.innerHTML = '<span class="spin"></span> 準備中...';

  try {
    const r = await fetch(`${settings.apiBase}/prepare-download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: currentUrl,
        format: selectedFormat,
        quality: selectedQuality
      }),
      signal: AbortSignal.timeout(10000)
    });
    const d = await r.json();
    if (d.error) throw new Error(d.error);

    log('✔ サーバーで変換を開始しました', 'ok');
    log('   完了後、このPCのChromeダウンロードに保存します', 'info');

    const job = await waitForPreparedDownload(d.jobId);
    const downloadUrl = `${settings.apiBase}/file?id=${encodeURIComponent(d.jobId)}`;
    await startChromeDownload(downloadUrl, job.filename);
    log(`✔ Chromeのダウンロードに追加しました: ${job.filename || 'ファイル'}`, 'ok');
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
  logBox.classList.toggle('log-disabled', !nextSettings.showLog);
  formatSelect.value = selectedFormat;
  qualitySelect.value = selectedQuality;
  updateQualityState();
}

function updateQualityState() {
  const audioOnly = ['mp3', 'm4a'].includes(selectedFormat);
  qualitySelect.disabled = audioOnly;
}

function normalizeApiBase(value) {
  return String(value || DEFAULT_SETTINGS.apiBase).replace(/\/+$/, '');
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

async function readJsonResponse(response) {
  let data = {};
  try {
    data = await response.json();
  } catch {
    data = {};
  }
  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

function formatYtdlpError(message) {
  const text = String(message || '');
  if (text.includes('Sign in to confirm you’re not a bot') || text.includes("Sign in to confirm you're not a bot")) {
    return 'YouTubeにBot判定されています。サーバーPCのChromeでYouTubeにログインし、サーバーを再起動してください。';
  }
  if (text.includes('No supported JavaScript runtime could be found') || text.includes('n challenge solving failed')) {
    return 'YouTubeの再生URL解析に失敗しました。サーバーPCで `brew install deno` と `yt-dlp -U` を実行し、サーバーを再起動してください。起動ログに `JS runtime: deno` と `Remote components: ejs:npm` が出る必要があります。';
  }
  if (text.includes('Requested format is not available') || text.includes('Only images are available')) {
    return '動画形式を取得できませんでした。サーバーPCでDeno導入、yt-dlp更新、YouTubeログイン済みChromeを確認し、サーバーを再起動してください。';
  }
  return text;
}

async function waitForPreparedDownload(jobId) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < 30 * 60 * 1000) {
    const r = await fetch(`${settings.apiBase}/job?id=${encodeURIComponent(jobId)}`, {
      signal: AbortSignal.timeout(5000)
    });
    const job = await r.json();
    if (job.error) throw new Error(job.error);
    if (job.status === 'done') return job;
    if (job.status === 'error') throw new Error(job.error || 'ダウンロードに失敗しました');
    await sleep(2000);
  }
  throw new Error('ダウンロード準備がタイムアウトしました');
}

function startChromeDownload(url, filename) {
  const options = {
    url,
    conflictAction: 'uniquify',
    saveAs: false
  };
  const safeName = safeDownloadFilename(filename);
  if (safeName) options.filename = safeName;

  return new Promise((resolve, reject) => {
    chrome.downloads.download(options, downloadId => {
      const err = chrome.runtime.lastError;
      if (err) {
        reject(new Error(err.message));
        return;
      }
      resolve(downloadId);
    });
  });
}

function safeDownloadFilename(filename) {
  if (!filename || typeof filename !== 'string') return '';
  return filename.replace(/[\\/:*?"<>|]/g, '_').replace(/^\.+/, '').trim().slice(0, 240);
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function log(msg, type = '') {
  if (!settings.showLog) return;
  logBox.classList.add('show');
  const span = document.createElement('div');
  span.textContent = msg;
  if (type === 'ok')   span.className = 'log-ok';
  if (type === 'err')  span.className = 'log-err';
  if (type === 'info') span.className = 'log-info';
  logBox.appendChild(span);
  logBox.scrollTop = logBox.scrollHeight;
}
