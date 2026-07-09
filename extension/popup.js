const state = { productId: null };

const byId = (id) => document.getElementById(id);

async function settings() {
  const stored = await chrome.storage.local.get(["apiUrl", "token"]);
  return {
    apiUrl: byId("apiUrl").value || stored.apiUrl || "http://localhost:8000",
    token: byId("token").value || stored.token || "",
  };
}

async function detect() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url) throw new Error("No active product page");
  const config = await settings();
  await chrome.storage.local.set(config);
  const response = await fetch(`${config.apiUrl}/api/v1/catalog/resolve?url=${encodeURIComponent(tab.url)}`);
  if (!response.ok) throw new Error("This product page is not indexed yet");
  const product = await response.json();
  state.productId = product.id;
  byId("productName").textContent = product.name;
  byId("price").textContent = `${product.currency} ${(product.price_cents / 100).toFixed(2)}`;
  byId("target").value = product.price_cents;
  byId("product").hidden = false;
}

async function watch() {
  const config = await settings();
  if (!config.token) throw new Error("Paste a JWT from the CommercePulse login endpoint");
  const response = await fetch(`${config.apiUrl}/api/v1/catalog/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${config.token}` },
    body: JSON.stringify({ product_id: state.productId, target_price_cents: Number(byId("target").value) }),
  });
  if (!response.ok) throw new Error("Could not create the price watch");
  byId("status").textContent = "Price watch created.";
}

async function run(action) {
  byId("status").textContent = "Working…";
  try { await action(); } catch (error) { byId("status").textContent = error.message; }
}

byId("detect").addEventListener("click", () => run(detect));
byId("watch").addEventListener("click", () => run(watch));
chrome.storage.local.get(["apiUrl", "token"]).then((value) => {
  if (value.apiUrl) byId("apiUrl").value = value.apiUrl;
  if (value.token) byId("token").value = value.token;
});

