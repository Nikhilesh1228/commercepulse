chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({ apiUrl: "http://localhost:8000" });
});
