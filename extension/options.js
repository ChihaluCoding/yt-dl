const DEFAULT_SETTINGS = {
  apiBase: 'http://localhost:9876',
  format: 'mp4',
  quality: '720',
  autoLoadInfo: true,
  textSize: 'normal'
};

const form = document.getElementById('settings-form');
const apiBase = document.getElementById('api-base');
const format = document.getElementById('format');
const quality = document.getElementById('quality');
const autoLoadInfo = document.getElementById('auto-load-info');
const textSize = document.getElementById('text-size');
const resetBtn = document.getElementById('reset-btn');
const statusEl = document.getElementById('status');

document.addEventListener('DOMContentLoaded', restore);
form.addEventListener('submit', save);
resetBtn.addEventListener('click', reset);

async function restore() {
  const saved = await getSettings();
  applyToForm(saved);
}

async function save(event) {
  event.preventDefault();

  const next = {
    apiBase: normalizeApiBase(apiBase.value),
    format: format.value,
    quality: quality.value,
    autoLoadInfo: autoLoadInfo.checked,
    textSize: textSize.value
  };

  const error = validate(next);
  if (error) {
    setStatus(error, 'err');
    return;
  }

  await chrome.storage.sync.set(next);
  setStatus('保存しました。次にポップアップを開いたときから反映されます。', 'ok');
}

async function reset() {
  await chrome.storage.sync.set(DEFAULT_SETTINGS);
  applyToForm(DEFAULT_SETTINGS);
  setStatus('初期値に戻しました。', 'ok');
}

function getSettings() {
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

function applyToForm(settings) {
  apiBase.value = settings.apiBase;
  format.value = settings.format;
  quality.value = settings.quality;
  autoLoadInfo.checked = settings.autoLoadInfo;
  textSize.value = settings.textSize;
}

function normalizeApiBase(value) {
  return String(value || DEFAULT_SETTINGS.apiBase).trim().replace(/\/+$/, '');
}

function validate(settings) {
  let parsed;
  try {
    parsed = new URL(settings.apiBase);
  } catch {
    return 'ローカルサーバーURLが正しくありません。';
  }

  if (parsed.protocol !== 'http:') {
    return 'ローカルサーバーURLは http:// で始めてください。';
  }

  if (!isAllowedHost(parsed.hostname)) {
    return '接続先は localhost、127.0.0.1、または同じWi-Fi内のサーバーIPにしてください。';
  }

  if (!parsed.port) {
    return 'ポート番号を含めてください。例: http://localhost:9876';
  }

  return '';
}

function isAllowedHost(hostname) {
  if (['localhost', '127.0.0.1'].includes(hostname)) {
    return true;
  }

  return /^(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})$/.test(hostname);
}

function setStatus(message, type) {
  statusEl.textContent = message;
  statusEl.className = type;
}
