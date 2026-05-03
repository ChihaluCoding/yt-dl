// YouTube content script
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'GET_URL') sendResponse({ url: location.href });
  return true;
});
