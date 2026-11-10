/* 제주 동네가게 도우미 — 화면 동작
   홈·지도·일정·내 가게는 서버의 의사결정 모델을 바로 부른다 (AI 비용 0). 대화·만들기만 AI Agent를 쓴다. */

/* ================= 기본 ================= */
const API = (window.JEJU_API || "").replace(/\/$/, "");
const $ = (s, el = document) => el.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
async function api(path, opts) {
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `오류 ${r.status}`);
  return r.json();
}
const postJSON = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

/* ---------- 아이콘 ---------- */
const P = {
  home: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
  map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14"/>',
  calendar: '<rect x="4" y="5" width="16" height="16" rx="2"/><path d="M8 3v4M16 3v4M4 10h16"/>',
  chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.4A8 8 0 1 1 21 12z"/>',
  store: '<path d="M4 9 5.5 4h13L20 9M4 9v11h16V9M4 9h16M9 20v-6h6v6"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  pin: '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  car: '<path d="M4 13l2-6h12l2 6v4H4zM6 17v2M18 17v2"/><circle cx="8" cy="14.2" r=".8"/><circle cx="16" cy="14.2" r=".8"/>',
  mountain: '<path d="m3 20 6.5-11 4 6.5L16 12l5 8z"/>',
  waves: '<path d="M2 9c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2 2-2 4-2M2 15c2 0 2-2 4-2s2 2 4 2 2-2 4-2 2 2 4 2 2-2 4-2"/>',
  landmark: '<path d="M3 21h18M5 21V10M19 21V10M9.5 21V10M14.5 21V10M2 10l10-6 10 6z"/>',
  sparkles: '<path d="M12 3l1.8 4.7 4.7 1.8-4.7 1.8L12 16l-1.8-4.7-4.7-1.8 4.7-1.8zM19 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>',
  utensils: '<path d="M7 3v8a2 2 0 0 0 2 2v8M5 3v5M9 3v5M17 3c-1.7 0-3 2-3 5s1.3 4 3 4v9"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', x: '<path d="M6 6l12 12M18 6 6 18"/>',
  up: '<path d="m6 15 6-6 6 6"/>', down: '<path d="m6 9 6 6 6-6"/>', right: '<path d="m9 6 6 6-6 6"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  camera: '<path d="M4 7h3l2-3h6l2 3h3v13H4z"/><circle cx="12" cy="13" r="4"/>',
  send: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  route: '<circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h7a3.5 3.5 0 0 0 0-7H9a3.5 3.5 0 0 1 0-7h7"/>',
  flag: '<path d="M5 21V4h11l-2 4 2 4H5"/>', info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
  check: '<path d="m5 12 5 5 9-10"/>', alert: '<path d="M12 3 2 20h20zM12 10v4M12 17v.5"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M3 20a6 6 0 0 1 12 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a5 5 0 0 1 3 6"/>',
  trend: '<path d="M3 17l6-6 4 4 8-8M15 7h6v6"/>', refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6"/>',
  text: '<path d="M4 18 9 6l5 12M6 14h6M15 18l3-8 3 8M16 16h4"/>',
  megaphone: '<path d="M3 10v4h3l7 5V5L6 10zM16 9a4 4 0 0 1 0 6M19 6a8 8 0 0 1 0 12"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5zM3 13l9 5 9-5"/>', filter: '<path d="M4 5h16l-6 8v6l-4-2v-4z"/>',
  menu: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  heart: '<path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.1a4.3 4.3 0 0 1 7.5 2.7C19.5 15.4 12 20 12 20z"/>',
  share: '<circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="m8.2 10.8 7.6-4.4M8.2 13.2l7.6 4.4"/>',
  locate: '<circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="8"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2"/>',
};
const ic = (k, cls = "") => `<svg class="i ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${P[k] || ""}</svg>`;

/* ---------- 색·이름 ---------- */
const LV_COLOR = { "한산": "#2f8f5b", "보통": "#c58a14", "붐빔": "#d2453f" };
const KIND = {
  "관광지": { c: "var(--k-sight)", hex: "#6250d6", i: "landmark" }, "오름": { c: "var(--k-oreum)", hex: "#1baf7a", i: "mountain" },
  "해수욕장": { c: "var(--k-beach)", hex: "#2a78d6", i: "waves" }, "명소": { c: "var(--k-spot)", hex: "#e87ba4", i: "sparkles" },
  "식사": { c: "var(--k-food)", hex: "#d9580b", i: "utensils" },
};
const kdot = (kind) => `<span class="kdot" style="background:${(KIND[kind] || KIND["명소"]).c}">${ic((KIND[kind] || KIND["명소"]).i)}</span>`;
const LV = (lv) => `<span class="badge lv-${esc((lv || "none").replace(/\s/g, ""))}">${esc(lv || "정보 없음")}</span>`;
const NAVER_BADGE = (n) => n === "미등록 후보" ? `<span class="badge b-hidden">숨은 가게</span>`
  : n === "등록" ? `<span class="badge b-listed">네이버 등록</span>`
  : n === "다른 상호로 등록" ? `<span class="badge b-listed">네이버엔 다른 상호</span>`
  : `<span class="badge b-unknown">네이버 ${esc(n || "미확인")}</span>`;
const naverSearch = (q) => `https://map.naver.com/p/search/${encodeURIComponent(q)}`;
const routeTo = (name, lat, lng) => `https://map.kakao.com/link/to/${encodeURIComponent(name)},${lat},${lng}`;

/* ---------- 토스트·대화상자 ---------- */
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("on");
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("on"), 2600);
}
function dialog({ title, body = "", input = null, ok = "확인", cancel = "취소" }) {
  return new Promise((resolve) => {
    const bd = document.createElement("div"); bd.className = "backdrop";
    bd.innerHTML = `<div class="dialog" role="dialog" aria-modal="true"><h3>${esc(title)}</h3>${body ? `<p>${esc(body)}</p>` : ""}
      ${input !== null ? `<input type="text" value="${esc(input)}" aria-label="${esc(title)}">` : ""}
      <div class="acts">${cancel ? `<button class="btn ghost sm" data-r="0">${esc(cancel)}</button>` : ""}<button class="btn sea sm" data-r="1">${esc(ok)}</button></div></div>`;
    document.body.appendChild(bd);
    const inp = bd.querySelector("input"); (inp || bd.querySelector("[data-r='1']")).focus();
    const done = (v) => { bd.remove(); resolve(v); };
    bd.querySelectorAll("[data-r]").forEach((b) => (b.onclick = () => done(b.dataset.r === "1" ? (inp ? inp.value.trim() : true) : null)));
    bd.onclick = (e) => { if (e.target === bd) done(null); };
    bd.onkeydown = (e) => { if (e.key === "Escape") done(null); if (e.key === "Enter" && inp) done(inp.value.trim()); };
  });
}

/* ================= 상태 ================= */
const TABS = {
  tourist: [["home", "홈", "home"], ["map", "지도", "map"], ["plan", "일정", "calendar"], ["chat", "대화", "chat"]],
  owner: [["store", "내 가게", "store"], ["map", "지도", "map"], ["make", "만들기", "image"], ["chat", "대화", "chat"]],
};
const REGION_CHIPS = ["애월", "한림", "한경", "구좌", "조천", "성산", "표선", "남원", "안덕", "대정", "중문동", "서귀동", "연동", "노형동", "이도2동", "삼도2동"];
const SLOTS = ["아침", "점심", "오후", "저녁", "밤"];
let mode = store.get("mode", null), current = "";
const state = { regions: store.get("regions", ["애월", "한림", "한경"]), day: store.get("day", "today"), slot: store.get("slot", "점심") };
function dateFor(day) {
  if (/^\d{4}-\d{2}-\d{2}$/.test(day)) return day;
  const d = new Date();
  if (day === "tomorrow") d.setDate(d.getDate() + 1);
  if (day === "sat") d.setDate(d.getDate() + (((6 - d.getDay()) + 7) % 7 || 7));
  if (day === "sun") d.setDate(d.getDate() + ((7 - d.getDay()) % 7 || 7));
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
const dayLabel = (day) => ({ today: "오늘", tomorrow: "내일", sat: "이번 토요일", sun: "이번 일요일" }[day] || day);
const short = (n) => String(n).replace(/(읍|면)$/, "");
// 받침에 따라 조사 고르기: josa("애월", "이", "가") → "애월이"
const josa = (w, a, b) => { const c = String(w).charCodeAt(String(w).length - 1); return w + (c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? a : b); };
let renderSeq = 0;
/* 찜: 이 기기에만 저장 (로그인 없음) */
const FAV_KEYS = ["store_id", "name", "lat", "lng", "category", "region", "naver", "naver_name", "address", "level"];
const favs = { all: () => store.get("favs", []), has: (id) => favs.all().some((f) => f.store_id === id),
  toggle(s) { const a = favs.all(), on = a.some((f) => f.store_id === s.store_id);
    store.set("favs", on ? a.filter((f) => f.store_id !== s.store_id) : [Object.fromEntries(FAV_KEYS.map((k) => [k, s[k]])), ...a].slice(0, 50)); return !on; } };
const cardData = new Map();  // 카드 버튼 → 가게 정보  // 늦게 도착한 이전 화면 응답이 새 화면을 덮지 않게

/* ================= 탐색 ================= */
function renderNav() {
  const html = TABS[mode].map(([id, label, i]) => `<button data-go="${id}">${ic(i)}<span>${label}</span></button>`).join("");
  $("#sideNav").innerHTML = html + `<div class="foot">공공데이터 기반 AI Agent<br>혼잡은 과거 패턴 예측이며 실시간이 아니에요</div>`;
  $("#bottomNav").innerHTML = html;
  document.querySelectorAll("[data-go]").forEach((b) => (b.onclick = () => go(b.dataset.go)));
  document.querySelectorAll(".seg button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
}
function go(id) {
  current = id;
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === "v-" + id));
  document.querySelectorAll("[data-go]").forEach((b) => b.setAttribute("aria-current", b.dataset.go === id ? "page" : "false"));
  history.replaceState(null, "", "#" + id);
  $("#main").scrollTop = 0;
  ({ home: renderHome, map: renderMap, plan: renderPlan, store: renderStore, make: renderMake, chat: renderChatEmpty })[id]?.();
}
function setMode(m) {
  mode = m; store.set("mode", m); chat.sessionId = ""; $("#threadIn").innerHTML = "";
  renderNav(); go(TABS[m][0][0]);
}

/* ================= 공통 조각 ================= */
function filtersHTML(opts = {}) {
  const days = ["today", "tomorrow", "sat", "sun"];
  const sum = `${state.regions.map(short).join("·")} · ${dayLabel(state.day)}${opts.slot === false ? "" : " · " + state.slot}`;
  return `<div class="card filters collapsible" id="filters">
    <div class="filter-sum">${ic("filter")}<span class="what">${esc(sum)}</span><button class="btn ghost sm" data-open-filters>바꾸기</button></div>
    <div><label class="l">동네 · 여러 곳을 고르면 덜 붐비는 곳으로 나눠 추천해요 (최대 4곳)</label><div class="chips" data-ctl="regions">
      ${REGION_CHIPS.map((r) => `<button class="chip" data-v="${r}" aria-pressed="${state.regions.includes(r)}">${r}</button>`).join("")}</div></div>
    <div><label class="l">날짜</label><div class="chips" data-ctl="day">
      ${days.map((d) => `<button class="chip" data-v="${d}" aria-pressed="${state.day === d}">${dayLabel(d)}</button>`).join("")}
      <input type="date" data-ctl="date" value="${/^\d{4}/.test(state.day) ? state.day : ""}" aria-label="날짜 직접 고르기"></div></div>
    ${opts.slot === false ? "" : `<div><label class="l">시간</label><div class="chips" data-ctl="slot">
      ${SLOTS.map((s) => `<button class="chip" data-v="${s}" aria-pressed="${state.slot === s}">${s}</button>`).join("")}</div></div>`}
  </div>`;
}
function bindFilters(root, onChange) {
  const keepOpen = () => { onChange(); $("#filters")?.classList.add("open"); };
  root.querySelector("[data-open-filters]")?.addEventListener("click", () => $("#filters").classList.toggle("open"));
  root.querySelectorAll("[data-ctl=regions] .chip").forEach((b) => (b.onclick = () => {
    const v = b.dataset.v, on = state.regions.includes(v);
    if (on && state.regions.length === 1) return toast("동네를 하나 이상 골라 주세요");
    state.regions = on ? state.regions.filter((x) => x !== v) : [...state.regions, v].slice(-4);
    store.set("regions", state.regions); keepOpen();
  }));
  root.querySelectorAll("[data-ctl=day] .chip").forEach((b) => (b.onclick = () => { state.day = b.dataset.v; store.set("day", state.day); keepOpen(); }));
  const di = root.querySelector("[data-ctl=date]");
  if (di) di.onchange = () => { if (di.value) { state.day = di.value; store.set("day", state.day); keepOpen(); } };
  root.querySelectorAll("[data-ctl=slot] .chip").forEach((b) => (b.onclick = () => { state.slot = b.dataset.v; store.set("slot", state.slot); keepOpen(); }));
}
const PARTS = [["덜 붐빔", "var(--quiet)"], ["생활권 여유", "var(--sea)"], ["숨은 가게", "var(--accent)"], ["오래된 가게", "#8b6f47"]];
function placeLinks(s) {
  if (s.naver === "등록" || s.naver === "다른 상호로 등록" || s.lat == null)
    return `<a class="link-btn" href="${naverSearch((s.naver_name || s.name) + " " + (s.region || ""))}" target="_blank" rel="noopener">${ic("external")}네이버 지도</a>`;
  return `<button class="link-btn" data-loc="${s.lat},${s.lng}" data-name="${esc(s.name)}">${ic("pin")}위치</button>
    <a class="link-btn" href="${routeTo(s.name, s.lat, s.lng)}" target="_blank" rel="noopener">${ic("route")}길찾기</a>
    ${s.address ? `<a class="link-btn" href="${naverSearch("제주특별자치도 " + s.address)}" target="_blank" rel="noopener" title="상호가 바뀌었으면 지금 그 주소의 가게가 보여요">${ic("search")}이 주소 네이버로</a>` : ""}`;
}
function storeCard(s, opts = {}) {
  const sp = s.score_parts ? Object.values(s.score_parts) : [];
  const max = { "덜 붐빔": 0.35, "생활권 여유": 0.25, "숨은 가게": 0.2, "오래된 가게": 0.2 };
  const parts = s.score_parts ? PARTS.map(([k, c]) => {
    const v = s.score_parts[k] ?? 0, w = Math.round(Math.min(1, v / (max[k] * 1.6)) * 100);
    return `<div class="p" title="${k} ${v}"><span>${k}</span><i style="--w:${w}%;--c:${c}"></i></div>`;
  }).join("") : "";
  return `<div class="card store ${opts.rank ? "ranked" : ""}">
    ${opts.rank ? `<span class="rank">${opts.rank}</span>` : ""}
    <div class="top"><div class="ttl"><div class="name">${esc(s.name)}</div>
        ${s.naver_name ? `<div class="alias">네이버: ${esc(s.naver_name)}</div>` : ""}
        <div class="meta">${esc(s.category || "")} · ${esc(s.region || "")}${s.years_open != null ? ` · <span title="인허가일 기준 · 주인이 바뀌어도 이어질 수 있어요">인허가 ${Math.round(s.years_open)}년</span>` : ""}${s.distance_km != null ? ` · <b class="dist">${s.distance_km < 1 ? Math.round(s.distance_km * 1000) + "m" : s.distance_km + "km"} · 걸어서 ${s.walk_min}분</b>` : ""}</div></div>
      ${s.score != null ? `<div class="score" style="--v:${Math.round(s.score * 100)}" title="추천 점수"><b>${Math.round(s.score * 100)}</b><small>점</small></div>` : ""}</div>
    <div class="row">${NAVER_BADGE(s.naver)}${s.open_confidence === "확인됨" ? `<span class="badge b-ok">영업 확인</span>` : s.open_confidence === "확인 필요" ? `<span class="badge b-warn" title="인허가는 폐업 신고를 하지 않으면 영업으로 남아 있어요">방문 전 영업 확인</span>` : ""}</div>
    ${parts ? `<div class="parts">${parts}</div>` : ""}
    ${s.address ? `<div class="meta">${ic("pin")} ${esc(s.address)}</div>` : ""}
    <div class="acts">${placeLinks(s)}
      ${opts.ask !== false ? `<button class="link-btn" data-ask="${esc(s.name)} (${esc(s.region || "")}) 어떤 곳이에요? 언제 가면 덜 붐벼요?">${ic("chat")}AI에게</button>` : ""}
      ${s.store_id && s.lat != null ? (cardData.set(s.store_id, s), `<button class="link-btn fav" data-fav="${s.store_id}" aria-pressed="${favs.has(s.store_id)}">${ic("heart")}<span>${favs.has(s.store_id) ? "찜함" : "찜"}</span></button>`) : ""}
      ${s.store_id ? `<button class="link-btn quiet" data-closed="${s.store_id}" data-name="${esc(s.name)}">${ic("flag")}문 닫았어요</button>` : ""}</div>
  </div>`;
}
let focusOn = null;
function bindCards(root) {
  root.querySelectorAll("[data-ask]").forEach((b) => (b.onclick = () => askAI(b.dataset.ask)));
  root.querySelectorAll("[data-loc]").forEach((b) => (b.onclick = () => {
    const [lat, lng] = b.dataset.loc.split(",").map(Number); focusOn = { lat, lng, name: b.dataset.name }; go("map");
  }));
  root.querySelectorAll("[data-fav]").forEach((b) => (b.onclick = () => {
    const s = cardData.get(+b.dataset.fav); if (!s) return;
    const on = favs.toggle(s);
    document.querySelectorAll(`[data-fav="${s.store_id}"]`).forEach((x) => { x.setAttribute("aria-pressed", String(on)); x.querySelector("span").textContent = on ? "찜함" : "찜"; });
    toast(on ? `${s.name} 찜했어요 · 일정에 넣을 수 있어요` : "찜을 뺐어요");
    if (current === "home") renderFavs();
  }));
  root.querySelectorAll("[data-closed]").forEach((b) => (b.onclick = async () => {
    const ok = await dialog({ title: `'${b.dataset.name}' 문을 닫았나요?`, body: "알려 주시면 확인 전까지 추천에서 빼 둘게요.", ok: "네, 닫았어요" });
    if (!ok) return;
    try {
      const d = await postJSON("/api/report", { store_id: +b.dataset.closed, kind: "closed" });
      b.closest(".store")?.style.setProperty("opacity", ".45"); b.innerHTML = `${ic("check")}신고됨`; b.disabled = true; toast(d.message || "고마워요");
    } catch { toast("전송하지 못했어요. 다시 시도해 주세요."); }
  }));
}

/* ================= 첫 화면 (유형 고르기) ================= */
function showOnboard() {
  const o = document.createElement("div"); o.className = "onboard";
  o.innerHTML = `<div class="wrap"><h1>제주 동네가게 도우미</h1>
    <p class="lead">공공데이터로 덜 붐비는 동네 식당을 찾고, 동네 가게의 홍보를 돕는 AI예요.</p>
    <div class="pick">
      <button data-m="tourist"><span class="ic" style="background:var(--sea)">${ic("map")}</span><b>여행 왔어요</b><span>덜 붐비는 시간·동네 식당 추천, 하루 일정, 지도</span></button>
      <button data-m="owner"><span class="ic" style="background:var(--accent)">${ic("store")}</span><b>가게 사장님이에요</b><span>우리 동네 손님 분석, 네이버 등록 확인, 메뉴판·홍보 이미지</span></button>
    </div><p class="fine">언제든 위쪽에서 바꿀 수 있어요 · 혼잡은 과거 데이터 패턴으로 예측해요</p></div>`;
  document.body.appendChild(o);
  o.querySelectorAll("[data-m]").forEach((b) => (b.onclick = () => { o.remove(); setMode(b.dataset.m); }));
}

/* ================= 여행객 홈 ================= */
async function renderHome() {
  const v = $("#v-home"), seq = ++renderSeq;
  v.innerHTML = `<div class="hero" id="hero"><div class="eyebrow">${ic("clock")} ${esc(dayLabel(state.day))} ${esc(state.slot)} · 과거 패턴 예측</div>
      <h1>덜 붐비는 제주, 동네 식당으로</h1><p>고른 동네의 식당 혼잡과 도민 생활권을 함께 보고 골랐어요</p>
      <button class="btn hero-btn" id="nearBtn">${ic("locate")}내 주변 3km에서 찾기</button>
      <div class="hero-fine">위치는 버튼을 누를 때 한 번만, 약 100m 단위로 쓰고 저장하지 않아요</div></div>
    <div id="nearOut"></div>
    ${filtersHTML()}
    <h2 class="sec">${ic("trend")} 동네별 붐빔 <span class="hint">그 시간 식당 혼잡 · 3단계</span></h2>
    <div id="homeCrowd" class="card"><div class="skeleton"></div></div>
    <h2 class="sec">${ic("utensils")} 추천 동네 식당 <span class="hint">4가지 기준 점수 순</span></h2>
    <div class="legend" style="margin-bottom:10px">${PARTS.map(([k, c]) => `<span><i style="background:${c}"></i>${k}</span>`).join("")}</div>
    <div id="homeRec" class="grid c2"><div class="skeleton" style="height:180px"></div><div class="skeleton" style="height:180px"></div></div>
    <div id="favOut"></div>
    <div class="grid c2" style="margin-top:24px">
      <button class="tile" data-go2="plan"><span class="ic sea">${ic("calendar")}</span><b>하루 일정 짜기</b><span class="d">관광지·오름·해수욕장과 식당을 덜 붐비는 순서로, 실제 길찾기 시간까지</span></button>
      <button class="tile" data-go2="map"><span class="ic violet">${ic("map")}</span><b>지도로 보기</b><span class="d">동네 혼잡, 관광 장소, 숨은 식당 위치</span></button>
    </div>`;
  bindFilters(v, renderHome);
  v.querySelectorAll("[data-go2]").forEach((b) => (b.onclick = () => go(b.dataset.go2)));
  $("#nearBtn").onclick = findNearby;
  renderFavs();
  try {
    const rec = await api(`/api/recommend?regions=${encodeURIComponent(state.regions.join(","))}&when=${dateFor(state.day)}&time_slot=${encodeURIComponent(state.slot)}&limit=6`);
    if (seq !== renderSeq) return;
    const order = { "한산": 0, "보통": 1, "붐빔": 2 };
    const regs = rec.regions.filter((r) => !r.error).sort((a, b) => order[a.crowd_level] - order[b.crowd_level]);
    const best = regs[0];
    if (best) {
      const nm = short(best.region), sub = josa(nm, "이", "가").slice(nm.length);
      const worst = regs[regs.length - 1], tie = regs.length > 1 && best.crowd_level === worst.crowd_level;
      const when = `${esc(dayLabel(state.day))} ${esc(state.slot)}엔`;
      $("#hero h1").innerHTML = tie
        ? `${when} 고른 동네 모두 <em>${esc(best.crowd_level)}</em>이에요`
        : `${when} <em>${esc(nm)}</em>${best.crowd_level === "한산" ? sub + " 가장 한산해요" : best.crowd_level === "보통" ? sub + " 가장 덜 붐벼요" : "도 붐벼요. 시간을 바꿔 보세요"}`;
      const roomy = regs.filter((r) => r.balance === "여유").length;
      $("#hero").insertAdjacentHTML("beforeend", `<div class="stats"><div class="stat"><b>${rec.candidates.toLocaleString()}</b>후보 식당</div>
        <div class="stat"><b>${regs.filter((r) => r.crowd_level !== "붐빔").length}/${regs.length}</b>덜 붐비는 동네</div>
        ${tie ? `<div class="stat"><b>${roomy}/${regs.length}</b>생활권 여유</div>` : `<div class="stat"><b>${esc(short(worst.region))}</b>가장 붐빔</div>`}</div>`);
    }
    $("#homeCrowd").innerHTML = regs.map((r) => {
      const n = order[r.crowd_level] + 1;
      return `<div class="meter"><span class="name">${esc(short(r.region))}</span>
        <div class="steps" title="${esc(r.crowd_level)}">${[1, 2, 3].map((k) => `<i style="${k <= n ? `background:${LV_COLOR[r.crowd_level]}` : ""}"></i>`).join("")}</div>
        <span class="row">${LV(r.crowd_level)}<span class="badge plain ${r.balance === "과밀" ? "lv-붐빔" : r.balance === "주의" ? "lv-보통" : "b-unknown"}" title="도민 생활권 (방문/거주)">생활권 ${esc(r.balance || "")}</span></span></div>`;
    }).join("") + `<div class="source plain tiny">${esc(regs[0]?.when || "")} 기준 · 생활권 과밀 동네는 도민 생활 보호를 위해 덜 추천해요</div>`;
    $("#homeRec").innerHTML = rec.recommendations.map((s, i) => storeCard(s, { rank: i + 1 })).join("") +
      `<div class="source" style="grid-column:1/-1">${esc(rec.sources.join(", "))}</div>`;
    bindCards($("#homeRec"));
  } catch (e) { $("#homeRec").innerHTML = `<div class="error">${esc(e.message)}</div>`; $("#homeCrowd").innerHTML = ""; }
}

function renderFavs() {
  const f = favs.all(), box = $("#favOut"); if (!box) return;
  box.innerHTML = f.length ? `<h2 class="sec">${ic("heart")} 찜한 가게 <span class="hint">${f.length}곳 · 이 기기에만 저장</span></h2>
    <div class="grid c2" id="favList">${f.map((s) => storeCard(s)).join("")}</div>
    <div class="row" style="margin-top:10px"><button class="btn ghost sm" id="favPlan">${ic("calendar")}찜한 가게로 일정 짜기</button></div>` : "";
  if (!f.length) return;
  bindCards(box);
  $("#favPlan").onclick = () => { pendingFavPlan = true; go("plan"); };
}
async function findNearby() {
  const out = $("#nearOut"), btn = $("#nearBtn");
  if (!navigator.geolocation) return toast("이 브라우저는 위치를 쓸 수 없어요");
  btn.disabled = true; btn.innerHTML = `${ic("locate")}위치 확인 중…`;
  const pos = await new Promise((ok) => navigator.geolocation.getCurrentPosition(ok, () => ok(null), { timeout: 10000, maximumAge: 300000 }));
  btn.disabled = false; btn.innerHTML = `${ic("locate")}내 주변 3km에서 찾기`;
  if (!pos) return toast("위치를 받지 못했어요. 브라우저 위치 권한을 확인해 주세요");
  // 약 100m 단위로만 보낸다 (정밀 위치는 서버·접속 기록에 남기지 않음)
  const lat = Math.round(pos.coords.latitude * 1000) / 1000, lng = Math.round(pos.coords.longitude * 1000) / 1000;
  out.innerHTML = `<div class="skeleton" style="height:160px;margin-top:16px"></div>`;
  try {
    const r = await api(`/api/nearby?lat=${lat}&lng=${lng}&when=${dateFor(state.day)}&time_slot=${encodeURIComponent(state.slot)}`);
    out.innerHTML = `<h2 class="sec">${ic("locate")} 내 주변 동네 식당 <span class="hint">${esc(dayLabel(state.day))} ${esc(state.slot)} · 추천 점수 순 · 반경 ${r.radius_km}km</span></h2>
      ${r.recommendations.length ? `<div class="grid c2">${r.recommendations.slice(0, 6).map((s, i) => storeCard(s, { rank: i + 1 })).join("")}</div>`
        : `<div class="empty">반경 ${r.radius_km}km 안에 추천할 동네 식당이 없어요. 위에서 동네를 골라 보세요.</div>`}`;
    bindCards(out); out.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) { out.innerHTML = `<div class="error">${esc(e.message)}</div>`; }
}

/* ================= 지도 ================= */
let mapObj = null, mapLayers = {}, mapCache = { key: "", data: null };
const MAP_KINDS = [["lv-한산", "한산 동네", "#2f8f5b"], ["lv-보통", "보통 동네", "#c58a14"], ["lv-붐빔", "붐빔 동네", "#d2453f"]];
const POI_KINDS = ["관광지", "오름", "해수욕장", "명소"];
let mapOn = store.get("mapOn3", ["lv-한산", "lv-보통", "lv-붐빔", "관광지", "해수욕장", "명소", "stores"]);
const pinHTML = (kind, lv, small) => {
  const k = KIND[kind] || KIND["명소"];
  return `<div class="pin ${small ? "sm" : ""}"><svg class="body" viewBox="0 0 34 42"><path d="M17 40.5S2.5 26.5 2.5 16.5a14.5 14.5 0 0 1 29 0C31.5 26.5 17 40.5 17 40.5z" fill="${k.hex}" stroke="#fff" stroke-width="2.5"/></svg>
    <span class="g">${ic(k.i)}</span>${LV_COLOR[lv] ? `<span class="lv" style="background:${LV_COLOR[lv]}"></span>` : ""}</div>`;
};
function renderMap() {
  $("#mapBar").innerHTML = `<div class="chips">${MAP_KINDS.map(([k, l, c]) => `<button class="chip" data-k="${k}" aria-pressed="${mapOn.includes(k)}"><span class="sw" style="background:${c}"></span>${l}</button>`).join("")}</div>
    <span class="sep"></span>
    <div class="chips">${POI_KINDS.map((k) => `<button class="chip" data-k="${k}" aria-pressed="${mapOn.includes(k)}"><span class="sw" style="background:${KIND[k].hex}"></span>${k}</button>`).join("")}
      <button class="chip" data-k="stores" aria-pressed="${mapOn.includes("stores")}"><span class="sw" style="background:var(--accent)"></span>식당</button></div>
    <span class="sep"></span>
    <div class="chips">${SLOTS.map((s) => `<button class="chip" data-s="${s}" aria-pressed="${state.slot === s}">${s}</button>`).join("")}</div>`;
  $("#mapBar").querySelectorAll("[data-k]").forEach((b) => (b.onclick = () => {
    const k = b.dataset.k; mapOn = mapOn.includes(k) ? mapOn.filter((x) => x !== k) : [...mapOn, k]; store.set("mapOn3", mapOn);
    b.setAttribute("aria-pressed", String(mapOn.includes(k))); drawMap();
  }));
  $("#mapBar").querySelectorAll("[data-s]").forEach((b) => (b.onclick = () => { state.slot = b.dataset.s; store.set("slot", state.slot); renderMap(); }));
  if (!mapObj) {
    mapObj = L.map("map", { preferCanvas: true, zoomControl: false }).setView([33.38, 126.55], 10);
    L.control.zoom({ position: "bottomright" }).addTo(mapObj);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "© OpenStreetMap" }).addTo(mapObj);
    const stage = (z) => (z < 11 ? 0 : z < 12 ? 1 : z < 13 ? 2 : z < 15 ? 3 : 4);
    let last = stage(mapObj.getZoom());
    mapObj.on("zoomend", () => { const s = stage(mapObj.getZoom()); if (s !== last) { last = s; drawMap(); } });
    mapObj.on("click", () => closeSheet());
  }
  setTimeout(() => mapObj.invalidateSize(), 60);
  drawMap().then(() => {
    if (!focusOn) return;
    const f = focusOn; focusOn = null;
    mapObj.setView([f.lat, f.lng], 16);
    openSheet(`<h3>${esc(f.name)}</h3><p class="small muted">추천 목록에서 고른 가게</p><div class="row"><a class="btn primary sm" href="${routeTo(f.name, f.lat, f.lng)}" target="_blank" rel="noopener">${ic("route")}길찾기</a></div>`);
  });
}
function openSheet(html) {
  closeSheet();
  const s = document.createElement("div"); s.className = "sheet"; s.id = "sheet";
  s.innerHTML = `<button class="close" aria-label="닫기">${ic("x")}</button>${html}`;
  $(".map-wrap").appendChild(s); s.querySelector(".close").onclick = closeSheet;
}
function closeSheet() { $("#sheet")?.remove(); }
async function drawMap() {
  const key = `${dateFor(state.day)}|${state.slot}|${state.regions.join(",")}`;
  if (mapCache.key !== key) {
    $(".map-wrap").insertAdjacentHTML("beforeend", `<div class="map-hint" id="mapLoading">${ic("refresh")} 혼잡 예측을 불러오는 중…</div>`);
    try { mapCache = { key, data: await api(`/api/map?when=${dateFor(state.day)}&time_slot=${encodeURIComponent(state.slot)}&store_regions=${encodeURIComponent(state.regions.join(","))}`) }; }
    finally { $("#mapLoading")?.remove(); }
  }
  const d = mapCache.data, z = mapObj.getZoom();
  Object.values(mapLayers).forEach((l) => mapObj.removeLayer(l));
  mapLayers = {};
  // 동네 혼잡: 읍·면은 이름표, 시내 '동'은 멀리서 점·가까이서 이름표
  const areas = d.areas.filter((a) => mapOn.includes("lv-" + a.level));
  mapLayers.areas = L.layerGroup(areas.map((a) => {
    const m = z >= 12 || !a.name.endsWith("동")
      ? L.marker([a.lat, a.lng], { icon: L.divIcon({ className: "", html: `<div class="area-pill" style="background:${LV_COLOR[a.level]}">${esc(short(a.name))} ${esc(a.level)}</div>`, iconSize: null }), zIndexOffset: 1000 })
      : L.circleMarker([a.lat, a.lng], { radius: 8, color: "#fff", weight: 2, fillColor: LV_COLOR[a.level], fillOpacity: 1 });
    return m.on("click", (e) => { L.DomEvent.stopPropagation(e); openSheet(`<h3>${esc(a.name)}</h3><div class="row" style="margin:6px 0 10px">${LV(a.level)}<span class="small muted">${esc(a.when)} 식당 혼잡</span></div>
      <p class="small muted">과거 유동인구·외식 패턴으로 예측했어요 (실시간 아님)</p>
      <button class="btn ghost sm" data-ask-area="${esc(a.name)}">${ic("chat")}이 동네 덜 붐비는 식당 물어보기</button>`);
      $("[data-ask-area]").onclick = () => askAI(`${a.name} ${dayLabel(state.day)} ${state.slot}에 덜 붐비는 식당 추천해 주세요`); });
  })).addTo(mapObj);
  for (const k of POI_KINDS) {
    if (!mapOn.includes(k) || (k === "오름" && z < 11)) continue;
    const sz = z >= 12 ? 1 : 0.82;
    mapLayers[k] = L.layerGroup(d.pois.filter((p) => p.kind === k).map((p) => L.marker([p.lat, p.lng], {
      icon: L.divIcon({ className: "", html: pinHTML(k, p.level, sz < 1), iconSize: [34, 42], iconAnchor: [17, 41] }), zIndexOffset: 500,
    }).on("click", (e) => { L.DomEvent.stopPropagation(e); openSheet(`<div class="row" style="margin-bottom:6px">${kdot(p.kind)}<span class="small muted">${esc(p.kind)} · ${esc(p.emd)}</span></div>
      <h3>${esc(p.name)}</h3><div class="row" style="margin:6px 0 12px"><span class="small muted">이번 달</span>${LV(p.level)}</div>
      <div class="row"><a class="btn ghost sm" href="${naverSearch("제주 " + p.name)}" target="_blank" rel="noopener">${ic("external")}네이버 지도</a>
      <a class="btn ghost sm" href="${routeTo(p.name, p.lat, p.lng)}" target="_blank" rel="noopener">${ic("route")}길찾기</a></div>`); }))).addTo(mapObj);
  }
  $("#mapHint")?.remove();
  if (mapOn.includes("stores") && z < 13) $(".map-wrap").insertAdjacentHTML("beforeend", `<div class="map-hint" id="mapHint">${ic("search")} 확대하면 ${esc(state.regions.map(short).join("·"))} 식당이 보여요</div>`);
  if (mapOn.includes("stores") && z >= 13) {
    const sc = (n) => n === 0 ? "#d9580b" : n === 1 ? "#0f5c6e" : "#9a948a", r = z >= 15 ? 9 : 7;
    mapLayers.stores = L.layerGroup(d.stores.map((s) => L.circleMarker([s.lat, s.lng], { radius: s.naver_listed === 0 ? r + 1 : r, color: "#fff", weight: 2, fillColor: sc(s.naver_listed), fillOpacity: .95 })
      .on("click", (e) => { L.DomEvent.stopPropagation(e); openSheet(`<div class="row" style="margin-bottom:6px">${kdot("식사")}<span class="small muted">${esc(s.category || "")} · ${esc(s.emd || "")}</span></div>
        <h3>${esc(s.name)}</h3><div class="row" style="margin:6px 0 12px">${s.naver_listed === 0 ? NAVER_BADGE("미등록 후보") : s.naver_listed === 1 ? NAVER_BADGE("등록") : NAVER_BADGE("미확인")}</div>
        <div class="row">${s.naver_listed === 1 ? `<a class="btn ghost sm" href="${naverSearch(s.name + " " + (s.emd || ""))}" target="_blank" rel="noopener">${ic("external")}네이버 지도</a>` : ""}
        <a class="btn primary sm" href="${routeTo(s.name, s.lat, s.lng)}" target="_blank" rel="noopener">${ic("route")}길찾기</a></div>`); }))).addTo(mapObj);
  }
}

/* ================= 일정 ================= */
const planState = { start: store.get("pstart", "10:00"), stops: store.get("pstops", "3"), meals: store.get("pmeals", "점심"), kinds: store.get("pkinds", ["관광지", "오름", "해수욕장", "명소"]) };
let planMap = null, planStops = [], planMeta = {}, pendingFavPlan = false;
const favStop = (f) => ({ name: f.name, kind: "식사", lat: f.lat, lng: f.lng, store_id: f.store_id, category: f.category, naver: f.naver, naver_name: f.naver_name, base_level: f.level || "정보 없음", meal: "식사" });
const KEEP = ["name", "kind", "lat", "lng", "base_level", "level", "stay_min", "poi_id", "store_id", "meal", "category", "naver", "naver_name"];
const pick = (p) => Object.fromEntries(KEEP.filter((k) => p[k] !== undefined && p[k] !== null).map((k) => [k, p[k]]));
async function renderPlan() {
  const v = $("#v-plan");
  v.innerHTML = `<div class="page-head"><div class="grow"><h1>하루 일정</h1><p>덜 붐비는 관광 장소와 동네 식당을 이어 드려요. 순서·시간은 직접 고칠 수 있어요</p></div></div>
    ${filtersHTML({ slot: false })}
    <div class="card flat" style="margin-top:12px"><div class="row">
      <label class="small muted">출발 <select data-p="start">${["08:00", "09:00", "10:00", "11:00", "13:00"].map((t) => `<option ${t === planState.start ? "selected" : ""}>${t}</option>`).join("")}</select></label>
      <label class="small muted">장소 수 <select data-p="stops">${["2", "3", "4", "5"].map((n) => `<option ${n == planState.stops ? "selected" : ""}>${n}</option>`).join("")}</select></label>
      <label class="small muted">식사 <select data-p="meals">${["점심", "점심,저녁"].map((m) => `<option value="${m}" ${m === planState.meals ? "selected" : ""}>${m.replace(",", " + ")}</option>`).join("")}</select></label>
      <div class="chips" data-p="kinds">${POI_KINDS.map((k) => `<button class="chip" data-v="${k}" aria-pressed="${planState.kinds.includes(k)}"><span class="sw" style="background:${KIND[k].hex}"></span>${k}</button>`).join("")}</div>
    </div></div>
    <div class="plan-grid" style="margin-top:14px"><div id="planOut"><div class="skeleton" style="height:320px"></div></div>
      <div class="map-col"><div class="mini-map" id="planMap"></div></div></div>`;
  bindFilters(v, renderPlan);
  v.querySelectorAll("select[data-p]").forEach((s) => (s.onchange = () => { planState[s.dataset.p] = s.value; store.set("p" + s.dataset.p, s.value); renderPlan(); }));
  v.querySelectorAll("[data-p=kinds] .chip").forEach((b) => (b.onclick = () => {
    const k = b.dataset.v, on = planState.kinds.includes(k);
    if (on && planState.kinds.length === 1) return toast("장소 종류를 하나 이상 골라 주세요");
    planState.kinds = on ? planState.kinds.filter((x) => x !== k) : [...planState.kinds, k]; store.set("pkinds", planState.kinds); renderPlan();
  }));
  try {
    const q = new URLSearchParams({ regions: state.regions.join(","), when: dateFor(state.day), start: planState.start, stops: planState.stops, meals: planState.meals, kinds: planState.kinds.join(",") });
    const r = await api(`/api/itinerary?${q}`);
    if (pendingFavPlan) {  // 찜한 가게로 식사 자리를 바꿔 넣는다
      pendingFavPlan = false;
      const f = favs.all(); let k = 0;
      planStops = r.itinerary.map(pick).map((p) => (p.kind === "식사" && f[k] ? { ...favStop(f[k++]), meal: p.meal } : p));
      planMeta = r; if (k) { toast(`찜한 가게 ${k}곳을 식사 자리에 넣었어요`); return recalcPlan(); }
    }
    showPlan(r);
  } catch (e) { $("#planOut").innerHTML = `<div class="error">${esc(e.message)}</div>`; }
}
function timelineHTML(r, editable) {
  const n = r.itinerary.length;
  return r.itinerary.map((p, i) => {
    const k = KIND[p.kind] || KIND["명소"];
    const move = i && p.travel_min ? `<div class="move"><span></span><div class="line"></div><span>${ic("car")}${p.route === "길찾기" ? "" : "약 "}${p.travel_min}분 · ${p.distance_km}km${p.route === "길찾기" ? " · 네이버 길찾기" : " · 직선 추정"}</span></div>` : "";
    const link = p.kind === "식사" && p.naver !== "등록" && p.naver !== "다른 상호로 등록"
      ? `<a class="link-btn" href="${routeTo(p.name, p.lat, p.lng)}" target="_blank" rel="noopener">${ic("route")}길찾기</a>`
      : `<a class="link-btn" href="${naverSearch("제주 " + (p.naver_name || p.name))}" target="_blank" rel="noopener">${ic("external")}네이버</a>`;
    const tools = editable ? `<select data-stay="${i}" aria-label="머무는 시간">${[30, 60, 90, 120, 180].map((m) => `<option value="${m}" ${m == p.stay_min ? "selected" : ""}>${m}분</option>`).join("")}</select>
      <button class="ib" data-up="${i}" ${i ? "" : "disabled"} title="앞으로" aria-label="앞으로">${ic("up")}</button>
      <button class="ib" data-down="${i}" ${i < n - 1 ? "" : "disabled"} title="뒤로" aria-label="뒤로">${ic("down")}</button>
      <button class="ib" data-del="${i}" title="빼기" aria-label="빼기">${ic("x")}</button>` : `<span class="small muted">${p.stay_min}분</span>`;
    return `${move}<div class="tl"><div class="time">${esc(p.arrive)}</div><div class="dot" style="background:${k.c}">${ic(k.i)}</div>
      <div class="body"><div class="row"><span class="t">${esc(p.name)}</span>${LV(p.level)}${p.kind === "식사" && p.naver ? NAVER_BADGE(p.naver) : ""}</div>
        <div class="small muted">${esc(p.kind === "식사" ? `${p.meal && p.meal !== "식사" ? p.meal + " · " : ""}${p.category || "식당"}${p.naver_name ? " · 네이버: " + p.naver_name : ""}` : p.kind)}</div>
        <div class="tools">${tools}${link}</div></div></div>`;
  }).join("");
}
function showPlan(r) {
  planStops = r.itinerary.map(pick); planMeta = r;
  $("#planOut").innerHTML = `<div class="card">
      <div class="row" style="margin-bottom:12px"><div style="min-width:0;flex:1"><b>${esc((r.regions || state.regions).map(short).join(" · "))}</b>
        <div class="small muted">${esc(r.ends_at)} 끝 · 이동 ${r.total_travel_min}분</div></div>
        <label class="small muted">출발 <input type="time" id="planStart" value="${esc(r.itinerary[0]?.arrive || planState.start)}"></label></div>
      ${timelineHTML(r, true) || `<div class="empty">장소를 추가해 주세요</div>`}
      <div class="row" style="margin-top:14px"><button class="btn ghost sm" id="planAdd">${ic("plus")}장소·식당 추가</button><button class="btn ghost sm" id="planAuto">${ic("refresh")}자동으로 다시 짜기</button>
        <button class="btn ghost sm" id="planShare" style="margin-left:auto">${ic("share")}공유</button>
        <button class="btn sea sm" id="planAsk">${ic("chat")}AI에게 다듬기</button></div>
      <div id="planCands"></div>
      <div class="source">${(r.notes || []).filter(Boolean).map(esc).join(" · ")}${r.sources?.length ? " · " + esc(r.sources.join(", ")) : ""}</div></div>`;
  drawPlanMap(r);
  const v = $("#planOut");
  v.querySelectorAll("[data-up]").forEach((b) => (b.onclick = () => { const i = +b.dataset.up; [planStops[i - 1], planStops[i]] = [planStops[i], planStops[i - 1]]; recalcPlan(); }));
  v.querySelectorAll("[data-down]").forEach((b) => (b.onclick = () => { const i = +b.dataset.down; [planStops[i + 1], planStops[i]] = [planStops[i], planStops[i + 1]]; recalcPlan(); }));
  v.querySelectorAll("[data-del]").forEach((b) => (b.onclick = () => { planStops.splice(+b.dataset.del, 1); recalcPlan(); toast("일정에서 뺐어요"); }));
  v.querySelectorAll("[data-stay]").forEach((sel) => (sel.onchange = () => { planStops[+sel.dataset.stay].stay_min = +sel.value; recalcPlan(); }));
  $("#planStart").onchange = () => recalcPlan();
  $("#planAuto").onclick = () => renderPlan();
  $("#planAdd").onclick = () => showCandidates();
  $("#planShare").onclick = () => sharePlan(r);
  $("#planAsk").onclick = () => askAI(`이 일정 어때요? 덜 붐비게 바꿀 점이 있으면 알려 주세요: ${r.itinerary.map((p) => `${p.arrive} ${p.name}`).join(" → ")} (${state.regions.join(", ")}, ${dayLabel(state.day)})`);
}
async function sharePlan(r) {
  const head = `제주 하루 일정 · ${(r.regions || state.regions).map(short).join("·")} · ${dayLabel(state.day)}`;
  const body = r.itinerary.map((p) => `${p.arrive} ${p.name}${p.kind === "식사" ? ` (${p.category || "식사"})` : ` (${p.kind})`}${p.lat != null ? `\n   길찾기 ${routeTo(p.name, p.lat, p.lng)}` : ""}`).join("\n");
  const text = `${head}\n\n${body}\n\n이동 ${r.total_travel_min}분 · ${r.ends_at} 끝 · 혼잡은 과거 데이터 예측`;
  try {
    if (navigator.share) { await navigator.share({ title: head, text }); return; }
    await navigator.clipboard.writeText(text); toast("일정을 복사했어요. 메신저에 붙여넣으세요");
  } catch (e) { if (e?.name !== "AbortError") await dialog({ title: "일정 복사", body: "아래 글을 복사하세요", input: text.replace(/\n\s*/g, " / "), cancel: null, ok: "닫기" }); }
}
async function recalcPlan() {
  $("#planOut").style.opacity = .55;
  try {
    const r = await postJSON("/api/itinerary/schedule", { stops: planStops, start: $("#planStart")?.value || planState.start });
    r.regions = planMeta.regions; showPlan(r);
  } catch (e) { toast(e.message); }
  finally { $("#planOut").style.opacity = 1; }
}
async function showCandidates() {
  const box = $("#planCands"); box.innerHTML = `<div class="skeleton" style="margin-top:12px"></div>`;
  const c = await api(`/api/itinerary/candidates?regions=${encodeURIComponent(state.regions.join(","))}&when=${dateFor(state.day)}`);
  const inPlan = new Set(planStops.map((p) => p.name));
  const item = (p, t, i) => inPlan.has(p.name) ? "" : `<button class="cand" data-type="${t}" data-i="${i}"><span class="n">${kdot(p.kind)}<span>${esc(p.name)}</span></span>${LV(p.level)}</button>`;
  const fl = favs.all().map(favStop);
  box.innerHTML = `<div class="cands">${fl.length ? `<div><b class="small">${ic("heart")} 찜한 가게</b>${fl.map((p, i) => item(p, "f", i)).join("") || `<div class="small muted">모두 일정에 있어요</div>`}</div>` : ""}
    <div><b class="small">추천 식당</b>${c.restaurants.map((p, i) => item(p, "r", i)).join("") || `<div class="small muted">없음</div>`}</div>
    <div><b class="small">관광 장소 · 덜 붐비는 순</b>${c.pois.map((p, i) => item(p, "p", i)).join("") || `<div class="small muted">없음</div>`}</div></div>`;
  box.querySelectorAll(".cand").forEach((b) => (b.onclick = () => {
    const p = ({ r: c.restaurants, p: c.pois, f: fl })[b.dataset.type][+b.dataset.i];
    planStops.push(pick(p)); recalcPlan(); toast(`${p.name} 추가했어요`);
  }));
}
function drawPlanMap(r) {
  if (planMap) { planMap.remove(); planMap = null; }
  if (!r.itinerary.length || !$("#planMap")) return;
  planMap = L.map("planMap", { zoomControl: false });
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "© OpenStreetMap" }).addTo(planMap);
  r.itinerary.forEach((p, i) => {
    if (i) {
      const seg = p.path?.length ? p.path : [[r.itinerary[i - 1].lat, r.itinerary[i - 1].lng], [p.lat, p.lng]];
      L.polyline(seg, p.path?.length ? { color: "#0f5c6e", weight: 5, opacity: .85 } : { color: "#0f5c6e", weight: 3, dashArray: "6 6" }).addTo(planMap);
    }
    L.marker([p.lat, p.lng], { icon: L.divIcon({ className: "", html: pinHTML(p.kind, p.level), iconSize: [34, 42], iconAnchor: [17, 41] }) })
      .bindTooltip(`${i + 1}. ${p.name} · ${p.arrive}`, { direction: "top", offset: [0, -36] }).addTo(planMap);
  });
  planMap.fitBounds(L.latLngBounds(r.itinerary.map((p) => [p.lat, p.lng])).pad(0.25));
}

/* ================= 사장님: 내 가게 ================= */
async function renderStore() {
  const v = $("#v-store"), sid = store.get("myStore", null);
  if (!sid) {
    v.innerHTML = `<div class="page-head"><div class="grow"><h1>내 가게 등록</h1><p>가게 이름으로 한 번만 찾아 두면 손님 분석과 홍보물 만들기를 바로 쓸 수 있어요</p></div></div>
      <div class="card"><form id="findForm" class="row"><input type="search" id="findName" placeholder="가게 이름 (예: 고이정)" style="flex:2;min-width:180px" required>
        <input type="text" id="findAddr" placeholder="동네·주소 일부 (선택)" style="flex:1;min-width:140px"><button class="btn sea">${ic("search")}찾기</button></form>
        <div class="search-results" id="findOut"></div></div>`;
    $("#findForm").onsubmit = async (e) => {
      e.preventDefault(); $("#findOut").innerHTML = `<div class="skeleton"></div>`;
      try {
        const r = await api(`/api/stores/find?name=${encodeURIComponent($("#findName").value)}&address_hint=${encodeURIComponent($("#findAddr").value)}`);
        $("#findOut").innerHTML = r.matches.length ? r.matches.map((m) => `<button data-id="${m.store_id}" data-name="${esc(m.name)}"><b>${esc(m.name)}</b>${m.naver_name && m.naver_name !== m.name ? `<span class="small" style="color:var(--sea)">네이버: ${esc(m.naver_name)}</span>` : ""}<span class="small muted">${esc(m.category || "")} · ${esc(m.address)}</span></button>`).join("")
          : `<div class="empty">찾지 못했어요. 이름을 다르게 적거나 동네를 넣어 보세요.</div>`;
        $("#findOut").querySelectorAll("[data-id]").forEach((b) => (b.onclick = () => { store.set("myStore", +b.dataset.id); store.set("myStoreName", b.dataset.name); renderStore(); }));
      } catch (err) { $("#findOut").innerHTML = `<div class="error">${esc(err.message)}</div>`; }
    };
    return;
  }
  v.innerHTML = `<div class="skeleton" style="height:120px"></div><div class="skeleton" style="height:220px;margin-top:12px"></div>`;
  let d;
  try { d = await api(`/api/store/${sid}`); } catch (e) { v.innerHTML = `<div class="error">${esc(e.message)}</div>`; return; }
  const s = d.store, ins = d.insight || {}, nv = d.naver || {};
  store.set("myStoreName", s.name);
  const years = s.open_date ? Math.max(0, Math.floor((Date.now() - new Date(s.open_date)) / 3.156e10)) : "-";
  const mix = ins.population_mix || {}, mixC = { "거주": "#0f5c6e", "근무": "#8b6f47", "방문": "#d9580b" };
  const slots = Object.entries(ins.meal_time_share || {}), smax = Math.max(...slots.map(([, x]) => parseInt(x)), 1);
  const grid = {}; (d.crowd?.forecast || []).forEach((f) => { (grid[f.weekday] ||= {})[f.time_slot] = f.level; });
  const tsl = [...new Set((d.crowd?.forecast || []).map((f) => f.time_slot))];
  const st = nv.naver_status || "미확인", who = esc(s.name);
  v.innerHTML = `
    <div class="card"><div class="store-head"><div class="av">${ic("store")}</div>
      <div style="min-width:0;flex:1"><h1 style="margin:0;font-size:1.4em">${who}</h1>
        <div class="small muted">${esc(s.category || "")} · ${esc(s.city)} ${esc(s.emd)} · <span title="인허가일 기준 · 주인이 바뀌어도 이어질 수 있어요">인허가 ${years}년</span> · ${esc((s.addr_road || s.addr_jibun || "").replace("제주특별자치도 ", "").split(",")[0])}</div>
        <div class="row" style="margin-top:6px">${st === "등록" ? NAVER_BADGE("등록") : st === "다른 상호로 등록" && nv.owner_confirmed ? NAVER_BADGE("다른 상호로 등록") : st === "미등록 후보" ? `<span class="badge b-hidden">네이버 지도에 없음</span>` : st === "다른 상호로 등록" ? `<span class="badge b-warn">네이버 확인 필요</span>` : NAVER_BADGE(st)}${nv.naver_match?.title && nv.naver_match.title !== s.name && (st === "등록" || nv.owner_confirmed) ? `<span class="small muted">네이버: ${esc(nv.naver_match.title)}</span>` : ""}</div></div>
      <button class="btn ghost sm" id="changeStore">가게 바꾸기</button></div></div>
    <div class="kpis" style="margin-top:12px">
      <div class="kpi"><span class="l">${ic("calendar")}손님 많은 요일</span><span class="v">${esc(ins.busiest_day || "-")}</span></div>
      <div class="kpi"><span class="l">${ic("users")}많이 오는 방문객</span><span class="v">${esc((ins.top_visitor_groups || [])[0] || "-")}</span></div>
      <div class="kpi"><span class="l">${ic("clock")}가장 바쁜 시간</span><span class="v">${esc((slots.sort((a, b) => parseInt(b[1]) - parseInt(a[1]))[0] || ["-"])[0])}</span></div>
      <div class="kpi"><span class="l">${ic("store")}동네 영업 식당</span><span class="v">${esc((ins.stores?.open ?? "-").toLocaleString())}곳</span></div></div>
    ${naverCardHTML(st, nv, who)}
    <h2 class="sec">바로 하기</h2>
    <div class="grid c3">
      <button class="tile" data-ask="${who} 사장이에요. 이번 주말에 인스타그램에 올릴 홍보 이미지 만들어 주세요"><span class="ic accent">${ic("megaphone")}</span><b>홍보 이미지</b><span class="d">손님층·리뷰 근거로 문구와 제주 배경까지</span></button>
      <button class="tile" data-photo="${who}"><span class="ic sea">${ic("camera")}</span><b>메뉴판 만들기</b><span class="d">메뉴판 사진 한 장이면 돼요</span></button>
      <button class="tile" data-today="${who}"><span class="ic green">${ic("utensils")}</span><b>오늘의 메뉴</b><span class="d">오늘 내놓는 메뉴를 한 장으로</span></button></div>
    <h2 class="sec">${ic("users")} 우리 동네 사람들 <span class="hint">${esc(s.emd)} · 유동인구 구성 (583)</span></h2>
    <div class="card"><div class="stack">${Object.entries(mix).map(([k, val]) => `<i style="width:${esc(val)};background:${mixC[k]}" title="${esc(k)} ${esc(val)}">${parseInt(val) >= 12 ? `${esc(k)} ${esc(val)}` : ""}</i>`).join("")}</div>
      <div class="legend" style="margin-top:10px">${Object.entries(mix).map(([k, val]) => `<span><i style="background:${mixC[k]}"></i>${esc(k)} ${esc(val)}</span>`).join("")}</div>
      <p class="small muted" style="margin:10px 0 0">방문객 많은 층: ${esc((ins.top_visitor_groups || []).join(", "))} · 최근 1년 동네 개업 ${esc(ins.stores?.opened_last_1y ?? "-")}곳 / 폐업 ${esc(ins.stores?.closed_last_1y ?? "-")}곳</p></div>
    <div class="grid c2" style="margin-top:12px">
      <div class="card"><h3>${ic("clock")} 식당 손님이 오는 시간</h3><div class="bars">${Object.entries(ins.meal_time_share || {}).map(([k, val]) => `<div class="bar ${parseInt(val) === smax ? "peak" : ""}" title="${esc(k)} ${esc(val)}"><span>${esc(k)}</span><div class="track"><div class="fill" style="width:${(parseInt(val) / smax) * 100}%"></div></div><span class="v">${esc(val)}</span></div>`).join("")}</div>
        <div class="source plain tiny">2019년 외식업 POS 비율 + 최근 카드 보정 (490·502)</div></div>
      <div class="card"><h3>${ic("calendar")} 요일 × 시간 혼잡</h3><div class="heat"><div class="h"></div>${tsl.map((t) => `<div class="h">${esc(t.split(" ")[0])}</div>`).join("")}
        ${Object.entries(grid).map(([day, row]) => `<div class="h">${esc(day[0])}</div>${tsl.map((t) => `<div class="lv-${esc(row[t])}" title="${esc(day)} ${esc(t)}: ${esc(row[t])}">${esc((row[t] || "")[0] || "")}</div>`).join("")}`).join("")}</div>
        <div class="legend" style="margin-top:10px">${["한산", "보통", "붐빔"].map((l) => `<span><i style="background:${LV_COLOR[l]}"></i>${l}</span>`).join("")}</div></div>
    </div>
    ${d.reviews ? `<h2 class="sec">${ic("chat")} 손님 리뷰 요약 <span class="hint">${d.reviews.with_text}건 · 평균 ★${d.reviews.avg_stars} · 2021년 자료</span></h2>
      <div class="grid c2"><div class="card"><h3 style="color:var(--quiet)">${ic("check")} 좋다는 점</h3>${d.reviews.strengths.slice(0, 3).map((x) => `<div style="margin-top:10px"><b>${esc(x.factor)}</b> <span class="small muted">${x.count}건</span>${x.examples.slice(0, 1).map((q) => `<div class="quote">“${esc(q)}”</div>`).join("")}</div>`).join("")}</div>
      <div class="card"><h3 style="color:var(--busy)">${ic("alert")} 아쉽다는 점</h3>${d.reviews.complaints.slice(0, 3).map((x) => `<div style="margin-top:10px"><b>${esc(x.factor)}</b> <span class="small muted">${x.count}건</span>${x.examples.slice(0, 1).map((q) => `<div class="quote">“${esc(q)}”</div>`).join("")}</div>`).join("")}</div></div>` : ""}
    ${newNearbyHTML(d.new_nearby, s)}
    <h2 class="sec">${ic("chat")} 받은 리뷰 붙여넣어 분석 <span class="hint">네이버·배달앱 리뷰를 한 줄에 하나씩 · 저장하지 않아요</span></h2>
    <div class="card"><textarea id="rvText" rows="5" placeholder="예)&#10;국물이 진하고 맛있어요&#10;주차가 좀 불편해요&#10;사장님이 친절하세요"></textarea>
      <div class="row" style="margin-top:10px"><button class="btn sea sm" id="rvGo">${ic("search")}분석하기</button><span class="small muted">AI 비용 없이 규칙으로 바로 나눠요</span></div>
      <div id="rvOut"></div></div>
    ${d.drafts.length ? `<h2 class="sec">${ic("image")} 만든 것 <span class="hint">초안·확정 이력</span></h2><div class="grid c2">${d.drafts.slice(0, 6).map((x) => `<div class="card flat small"><div class="row"><b>${esc(x.kind_label)}</b><span class="badge ${x.status === "approved" ? "b-ok" : "b-warn"}">${x.status === "approved" ? "확정" : x.status === "pending" ? "미리보기" : esc(x.status)}</span></div><div class="muted">${esc((x.title || x.body || "").slice(0, 70))}</div></div>`).join("")}</div>` : ""}
    <div class="source">${esc([...(ins.sources || []), ...(nv.sources || [])].filter((x, i, a) => a.indexOf(x) === i).join(", "))}</div>`;
  $("#changeStore").onclick = () => { store.set("myStore", null); renderStore(); };
  bindNaverCard(v, sid);
  $("#rvGo").onclick = async () => {
    const text = $("#rvText").value.trim(); if (!text) return toast("리뷰를 붙여넣어 주세요");
    $("#rvOut").innerHTML = `<div class="skeleton" style="margin-top:12px"></div>`;
    try {
      const r = await postJSON("/api/reviews/analyze", { text });
      const col = (list, title, color, icn) => `<div><h3 style="color:${color}">${ic(icn)} ${title}</h3>${list.length ? list.map((x) => `<div style="margin-top:10px"><b>${esc(x.factor)}</b> <span class="small muted">${x.count}건 · ${esc(x.share)}</span>${x.examples.slice(0, 1).map((q) => `<div class="quote">“${esc(q)}”</div>`).join("")}</div>`).join("") : `<div class="small muted" style="margin-top:8px">없음</div>`}</div>`;
      $("#rvOut").innerHTML = `<div class="grid c2" style="margin-top:14px">${col(r.strengths, "좋다는 점", "var(--quiet)", "check")}${col(r.complaints, "아쉽다는 점", "var(--busy)", "alert")}</div>
        <div class="row" style="margin-top:12px"><span class="small muted">리뷰 ${r.reviews}건 분석</span>
        <button class="btn ghost sm" id="rvAsk" style="margin-left:auto">${ic("megaphone")}이 강점으로 홍보 문구 만들기</button></div>`;
      $("#rvAsk").onclick = () => askAI(`${s.name} 사장이에요. 손님 리뷰를 붙여넣을게요. 분석해서 강점으로 홍보 문구 만들어 주세요.\n${text.slice(0, 3000)}`);
    } catch (e) { $("#rvOut").innerHTML = `<div class="error">${esc(e.message)}</div>`; }
  };
  bindCards(v);
  v.querySelectorAll("[data-photo]").forEach((b) => (b.onclick = () => { pendingPhotoText = `${b.dataset.photo} 메뉴판이에요. 보기 좋게 다시 만들어 주세요`; $("#file").click(); }));
  v.querySelectorAll("[data-today]").forEach((b) => (b.onclick = () => { go("chat"); $("#input").value = `${b.dataset.today} 오늘의 메뉴 이미지 만들어 주세요. 메뉴는 `; $("#input").focus(); autoGrow(); }));
}

/* 네이버 등록 상태: 인허가 상호와 네이버 상호가 다른 가게 (간판을 바꾼 경우 등) */
function naverCardHTML(st, nv, who) {
  if (st === "등록" || (st === "다른 상호로 등록" && nv.owner_confirmed)) return "";
  const box = (body, acts) => `<div class="card naver-card"><div class="row"><span class="kdot" style="background:var(--accent)">${ic("alert")}</span>
    <div style="flex:1;min-width:0">${body}</div></div><div class="row" style="margin-top:12px">${acts}</div></div>`;
  if (st === "다른 상호로 등록") {
    return box(`<b>같은 주소에 네이버 '${esc(nv.naver_match.title)}'이 있어요</b><div class="small muted">${esc(nv.naver_match.road_address || "")} · 사장님 가게가 맞나요? 맞으면 앞으로 네이버 이름으로 안내·홍보해요</div>`,
      `<button class="btn sea sm" data-nv-yes="${esc(nv.naver_match.title)}">${ic("check")}네, 우리 가게예요</button><button class="btn ghost sm" data-nv-no>아니에요</button>`);
  }
  return box(`<b>네이버 지도에서 이 이름으로 찾을 수 없어요</b><div class="small muted">간판·네이버 이름이 사업자 등록 이름과 다르면 알려 주세요. 주소로 확인해 연결해요</div>`,
    `<button class="btn sea sm" data-nv-other>${ic("search")}다른 이름으로 이미 등록돼 있어요</button>
     <button class="btn ghost sm" data-ask="${who} 네이버 지도에 아직 없어요. 등록 자료 정리해 주세요">등록 자료 받기</button>`);
}
function bindNaverCard(root, sid) {
  const link = async (name, confirm = true) => {
    const btns = root.querySelectorAll(".naver-card button");
    btns.forEach((b) => (b.disabled = true));
    const first = btns[0], label = first?.innerHTML;
    if (first) first.innerHTML = `${ic("refresh")}네이버에서 확인 중…`;
    try {
      const r = await postJSON("/api/naver/link", { store_id: sid, naver_name: name, confirm });
      if (r.linked || !confirm) { toast(r.message); return renderStore(); }
      const c = (r.naver_candidates || []).map((x) => `${x.title} (${(x.road_address || "").replace("제주특별자치도 ", "")})`).join(", ");
      await dialog({ title: "주소가 달라서 연결하지 않았어요", body: `우리 가게 주소: ${r.our_address}. ${c ? "네이버에서 찾은 가게: " + c : "그 이름으로 찾은 가게가 없어요."} 이름을 다시 확인해 주세요.`, cancel: null, ok: "확인" });
    } catch (e) { toast(e.message); }
    btns.forEach((b) => (b.disabled = false)); if (first) first.innerHTML = label;
  };
  root.querySelector("[data-nv-yes]")?.addEventListener("click", (e) => link(e.currentTarget.dataset.nvYes));
  root.querySelector("[data-nv-no]")?.addEventListener("click", () => link("", false));
  root.querySelector("[data-nv-other]")?.addEventListener("click", async () => {
    const name = await dialog({ title: "네이버 지도에 올라간 가게 이름", body: "네이버 지도에서 보이는 이름을 적어 주세요. 주소가 같을 때만 연결해요.", input: "", ok: "확인하기" });
    if (name) link(name);
  });
}

function newNearbyHTML(n, s) {
  if (!n) return "";
  const rows = n.stores.slice(0, 8).map((x) => `<div class="nb ${x.category === s.category ? "same" : ""}"><b>${esc(x.name)}</b>
    <span class="small muted">${esc(x.category || "")} · ${esc(x.open_date)} 개업</span></div>`).join("");
  return `<h2 class="sec">${ic("sparkles")} 우리 동네 새로 생긴 가게 <span class="hint">${esc(s.emd)} · 최근 1년 · 인허가 ${esc(n.as_of)} 기준</span></h2>
    <div class="card">${n.stores.length ? `<p class="small" style="margin:0 0 10px">같은 업종(${esc(s.category)}) <b>${n.same_category}곳</b>이 새로 문을 열었어요${n.same_category ? ". 우리 가게만의 강점을 더 드러내 보세요" : ""}</p>
      <div class="nbs">${rows}</div>` : `<div class="small muted">최근 1년 새로 연 가게가 없어요</div>`}</div>`;
}

/* ================= 사장님: 만들기 ================= */
function renderMake() {
  const v = $("#v-make"), name = store.get("myStore", null) ? store.get("myStoreName", "") : "", who = name || "제 가게";
  const gal = store.get("gallery", []);
  v.innerHTML = `<div class="page-head"><div class="grow"><h1>만들기</h1><p>AI가 데이터 근거로 초안을 만들고, 사장님이 확정하면 완성본이 나와요${name ? ` · <b>${esc(name)}</b>` : ""}</p></div></div>
    <div class="grid c2">
      <button class="tile" data-mk="promo"><span class="ic accent">${ic("megaphone")}</span><b>홍보 이미지 (인스타·네이버)</b><span class="d">손님층·붐비는 요일·리뷰 강점으로 문구를 정하고 제주 배경까지</span></button>
      <button class="tile" data-mk="menu"><span class="ic sea">${ic("camera")}</span><b>메뉴판 (사진으로)</b><span class="d">손글씨 메뉴판 사진 → 큰 글씨 메뉴판</span></button>
      <button class="tile" data-mk="today"><span class="ic green">${ic("utensils")}</span><b>오늘의 메뉴</b><span class="d">오늘 메뉴와 가격만 말해 주세요</span></button>
      <button class="tile" data-mk="listing"><span class="ic violet">${ic("map")}</span><b>네이버 지도 등록 자료</b><span class="d">인허가 정보로 채운 등록 준비물·소개글</span></button></div>
    <h2 class="sec">${ic("image")} 만든 이미지 <span class="hint">이 기기에서 확정한 것</span></h2>
    ${gal.length ? `<div class="gallery">${gal.slice().reverse().map((g) => `<a href="${esc(g.url)}" target="_blank" download><img src="${esc(g.url)}" alt="${esc(g.label)}" loading="lazy"><span>${esc(g.label)}</span></a>`).join("")}</div>` : `<div class="card empty">아직 만든 이미지가 없어요. 위에서 하나 골라 보세요</div>`}`;
  v.querySelectorAll("[data-mk]").forEach((b) => (b.onclick = () => {
    const k = b.dataset.mk;
    if (k === "menu") { pendingPhotoText = `${who} 메뉴판 사진이에요. 보기 좋게 다시 만들어 주세요`; $("#file").click(); return; }
    if (k === "today") { go("chat"); $("#input").value = `${who} 오늘의 메뉴 이미지 만들어 주세요. 메뉴는 `; $("#input").focus(); autoGrow(); return; }
    askAI(k === "promo" ? `${who} 이번 주말에 인스타그램에 올릴 홍보 이미지 만들어 주세요` : `${who} 네이버 지도에 등록하고 싶어요. 등록 자료 정리해 주세요`);
  }));
}

/* ================= 대화 ================= */
const chat = { sessionId: "", busy: false };
let attached = null, pendingPhotoText = "";
const STEP_LABEL = {
  find_store: "가게 찾기", search_stores: "가게 목록", area_insight: "동네 손님 분석", predict_crowd: "혼잡 예측", resident_balance: "생활권 확인",
  check_naver_listed: "네이버 등록 확인", analyze_reviews: "리뷰 분석", marketing_brief: "홍보 계획", save_draft: "초안 저장", decide_draft: "확정",
  render_card: "이미지 만들기", generate_background: "배경 그리기 (20초쯤)", list_drafts: "이전 기록", recommend_stores: "추천 점수 계산",
  plan_itinerary: "일정 짜기", place_crowd: "관광지 붐빔", make_listing_kit: "등록 자료 정리",
};
const FOLLOW = {
  predict_crowd: ["이 시간에 덜 붐비는 동네 식당 추천해 줘", "이 동네로 하루 일정 짜 줘"],
  recommend_stores: ["이 식당들로 하루 일정 짜 줘", "다른 동네랑 비교해 줘"],
  plan_itinerary: ["저녁도 넣어 줘", "오름 위주로 바꿔 줘"],
  check_naver_listed: ["네이버 지도 등록 자료 정리해 줘"],
  area_insight: ["이 손님층에 맞는 홍보 이미지 만들어 줘", "요일별로 언제 한산한지 알려 줘"],
  place_crowd: ["근처 덜 붐비는 식당도 알려 줘"],
};
const STARTERS = {
  tourist: [["clock", "토요일에 애월에서 점심 먹으려는데 언제 가면 덜 붐벼요?"], ["calendar", "한림·한경 하루 일정 짜 주세요. 점심은 현지 식당으로"], ["mountain", "성산일출봉 이번 달에 붐벼요? 언제 가면 좋아요?"]],
  owner: [["store", "애월 콩지쿡 사장인데 네이버 지도에 우리 가게 나와요?"], ["users", "연동에서 식당 하는데 우리 동네는 언제, 어떤 손님이 많아요?"], ["megaphone", "애월 고이정 사장이에요. 손님들이 뭐라고 하는지 보고 홍보 이미지 만들어 주세요"]],
};
function renderChatEmpty() {
  const t = $("#threadIn");
  if (t.children.length) return;
  t.innerHTML = `<div class="welcome-chat" id="intro"><div class="av">동</div>
    <h2>${mode === "owner" ? "사장님, 무엇을 도와드릴까요?" : "제주 여행, 무엇이든 물어보세요"}</h2>
    <p class="muted small">데이터를 직접 조회해 근거와 함께 답해요 · 글, ${ic("mic")} 말, ${ic("camera")} 사진 모두 돼요</p>
    <div class="starter">${STARTERS[mode].map(([i, s]) => `<button>${ic(i)}<span>${esc(s)}</span></button>`).join("")}</div></div>`;
  t.querySelectorAll(".starter button").forEach((b) => (b.onclick = () => send(b.textContent.trim())));
}
function askAI(text) { go("chat"); send(text); }

if (window.marked) marked.setOptions({ breaks: true, gfm: true });
function md(text) {
  let src = "", gls = "";
  const body = text.split("\n").filter((l) => {
    const t = l.replace(/^\**|\**$/g, "").trim();
    if (/^근거\s*[:：]/.test(t)) { src = t.replace(/^근거\s*[:：]\s*/, ""); return false; }
    if (/^※\s*용어/.test(t)) { gls = t; return false; }
    return true;
  }).join("\n");
  return DOMPurify.sanitize(marked.parse(body)) + (gls ? `<span class="gls">${esc(gls)}</span>` : "") + (src ? `<span class="src">근거 · ${esc(src)}</span>` : "");
}
const scrollDown = () => { const th = $("#thread"); th.scrollTo({ top: th.scrollHeight, behavior: "smooth" }); };
function addUser(text, img) {
  const m = document.createElement("div"); m.className = "msg user";
  m.innerHTML = `<div class="col">${img ? `<img class="attach" src="${img}" alt="첨부 사진">` : ""}${text ? `<div class="bubble">${esc(text)}</div>` : ""}</div>`;
  $("#threadIn").appendChild(m); scrollDown();
}
function newTurn() {
  const m = document.createElement("div"); m.className = "msg";
  m.innerHTML = `<div class="av">동</div><div class="col"><div class="steps"></div><div class="typing" aria-label="생각하는 중"><i></i><i></i><i></i></div></div>`;
  $("#threadIn").appendChild(m); scrollDown();
  return { el: m.querySelector(".col"), steps: m.querySelector(".steps"), bubble: null, text: "", tools: [] };
}
function widgetFor(name, r) {
  if (!r || r.error) return "";
  if (name === "predict_crowd" && r.forecast?.length) {
    if (r.forecast.length <= 5) return `<div class="card widget"><h3>${ic("clock")}${esc(r.region)} 식당 혼잡 <span class="small muted">${esc(r.forecast[0].weekday)}${r.date ? " · " + esc(r.date) : ""}</span></h3>
      <div class="heat" style="grid-template-columns:repeat(${r.forecast.length},minmax(0,1fr))">${r.forecast.map((f) => `<div class="h">${esc(f.time_slot.split(" ")[0])}</div>`).join("")}${r.forecast.map((f) => `<div class="lv-${esc(f.level)}">${esc(f.level)}</div>`).join("")}</div></div>`;
    const g = {}; r.forecast.forEach((f) => ((g[f.weekday] ||= {})[f.time_slot] = f.level));
    const ts = [...new Set(r.forecast.map((f) => f.time_slot))];
    return `<div class="card widget"><h3>${ic("calendar")}${esc(r.region)} 요일 × 시간 혼잡</h3><div class="heat"><div class="h"></div>${ts.map((t) => `<div class="h">${esc(t.split(" ")[0])}</div>`).join("")}
      ${Object.entries(g).map(([d, row]) => `<div class="h">${esc(d[0])}</div>${ts.map((t) => `<div class="lv-${esc(row[t])}">${esc((row[t] || "")[0] || "")}</div>`).join("")}`).join("")}</div></div>`;
  }
  if (name === "recommend_stores" && r.recommendations?.length) return `<div class="widget grid">${r.recommendations.slice(0, 4).map((s, i) => storeCard(s, { ask: false, rank: i + 1 })).join("")}</div>`;
  if (name === "plan_itinerary" && r.itinerary?.length) return `<div class="card widget"><h3>${ic("calendar")}${esc((r.regions || []).map(short).join(" · "))} 하루 일정 <span class="small muted">${esc(r.ends_at)} 끝 · 이동 ${r.total_travel_min}분</span></h3>${timelineHTML(r, false)}</div>`;
  if (name === "check_naver_listed" && r.naver_status) {
    return `<div class="card widget small"><div class="row"><b>네이버 지도</b>${r.naver_status === "등록" ? NAVER_BADGE("등록") : r.naver_status === "미등록 후보" ? `<span class="badge b-hidden">이 이름으로 없음</span>` : `<span class="badge b-warn">확인 필요</span>`}
      ${r.naver_match ? `<span class="muted">네이버: ${esc(r.naver_match.title)} · ${esc(r.naver_match.road_address || "")}</span>` : ""}</div></div>`;
  }
  if (name === "marketing_brief" && r.target_candidates) {
    return `<div class="card widget small"><h3>${ic("megaphone")}홍보 계획 · 데이터 근거</h3>
      <div><b>타깃 후보</b> ${r.target_candidates.map((t) => esc(t.who)).join(" · ")}</div>
      <div><b>올릴 때</b> ${r.posting_timing.map((t) => esc(t.when)).join(" · ")}</div>
      <div><b>메시지 재료</b> ${r.message_materials.map((m) => esc(m.angle)).join(" · ")}</div></div>`;
  }
  if (name === "make_listing_kit" && r.prefilled) {
    return `<div class="card widget small"><h3>${ic("map")}네이버 등록 자료</h3><table style="width:100%">${Object.entries(r.prefilled).map(([k, v]) => `<tr><td class="muted" style="padding:3px 10px 3px 0;white-space:nowrap">${esc(k)}</td><td>${esc(v || "-")}</td></tr>`).join("")}</table>
      <div style="margin-top:8px"><b>준비할 것</b><ul style="margin:4px 0 0;padding-left:1.2em">${r.owner_prepares.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div></div>`;
  }
  if (name === "place_crowd" && r.level) {
    return `<div class="card widget small"><div class="row">${kdot(r.kind)}<b>${esc(r.place)}</b><span class="muted">${r.month}월</span>${LV(r.level)}
      ${r.by_time_of_day ? Object.entries(r.by_time_of_day).map(([t, l]) => `<span class="badge plain lv-${esc(l)}">${esc(t)} ${esc(l)}</span>`).join("") : ""}</div>
      <div class="muted" style="margin-top:6px">한산한 달: ${r.quietest_months.map((m) => m + "월").join(", ") || "-"}</div></div>`;
  }
  return "";
}
function addCard(turn, r) {
  const url = API + "/api/cards/" + r.image.split("/").pop() + "?t=" + Date.now();
  const kind = { feed: "인스타그램 피드 1080×1080", story: "스토리 1080×1920", menu: "메뉴판 1080×1350" }[r.format] || "";
  const box = document.createElement("div"); box.className = "card card-out widget";
  box.innerHTML = `<img src="${url}" alt="${kind}"><div class="row small muted" style="margin-top:10px">
    <span class="badge ${r.preview_only ? "b-warn" : "b-ok"}">${r.preview_only ? "미리보기" : "확정"}</span>${kind}${r.uses_ai_background ? " · AI 생성 배경" : ""}
    <a class="link-btn" href="${url}" download style="margin-left:auto">${ic("down")}내려받기</a></div>`;
  if (r.preview_only) {
    const a = document.createElement("div"); a.className = "acts";
    a.innerHTML = `<button class="btn primary">${ic("check")}네, 이대로 확정해요</button><button class="btn ghost">고쳐 주세요</button>`;
    const [ok, ed] = a.querySelectorAll("button");
    ok.onclick = () => { a.querySelectorAll("button").forEach((b) => (b.disabled = true)); send("네, 이대로 확정해 주세요."); };
    ed.onclick = () => { $("#input").value = "이렇게 고쳐 주세요: "; $("#input").focus(); autoGrow(); };
    box.appendChild(a);
  } else {
    const gal = store.get("gallery", []); gal.push({ url: url.split("?")[0], label: kind, ts: Date.now() }); store.set("gallery", gal.slice(-40));
  }
  turn.el.appendChild(box); turn.bubble = null; scrollDown();
}
function appendText(turn, t) {
  turn.el.querySelector(".typing")?.remove();
  if (!turn.bubble) { turn.bubble = document.createElement("div"); turn.bubble.className = "bubble"; turn.text = ""; turn.el.appendChild(turn.bubble); }
  turn.text += t; turn.bubble.innerHTML = md(turn.text); scrollDown();
}
function showError(turn, msg) { turn.el.querySelector(".typing")?.remove(); const d = document.createElement("div"); d.className = "error"; d.textContent = msg; turn.el.appendChild(d); scrollDown(); }

async function chatFetch(fd) {
  let code = store.get("accessCode", "");
  let res = await fetch(API + "/api/chat", { method: "POST", body: fd, headers: code ? { "X-Access-Code": code } : {} });
  if (res.status === 401) {
    code = await dialog({ title: "데모 접속 코드", body: "제출 페이지에 안내된 접속 코드를 입력해 주세요.", input: "", ok: "들어가기" });
    if (!code) throw new Error("접속 코드가 필요해요.");
    store.set("accessCode", code);
    res = await fetch(API + "/api/chat", { method: "POST", body: fd, headers: { "X-Access-Code": code } });
    if (res.status === 401) { store.set("accessCode", ""); throw new Error("접속 코드가 맞지 않아요."); }
  }
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `오류 ${res.status}`);
  return res;
}
async function send(text) {
  if (chat.busy) return;
  if (current !== "chat") go("chat");
  text = (text ?? $("#input").value).trim();
  if (!text && !attached) return;
  chat.busy = true; $("#sendBtn").disabled = true;
  $("#intro")?.remove(); document.querySelectorAll(".follow").forEach((f) => f.remove());
  const file = attached;
  addUser(text, file ? URL.createObjectURL(file) : null);
  $("#input").value = ""; autoGrow(); clearAttach();
  const fd = new FormData();
  fd.append("message", text); fd.append("mode", mode); fd.append("session_id", chat.sessionId);
  if (file) fd.append("image", file);
  const turn = newTurn();
  try {
    const res = await chatFetch(fd);
    const reader = res.body.getReader(), dec = new TextDecoder(); let buf = "";
    for (;;) {
      const { value, done } = await reader.read(); if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
        if (!chunk.startsWith("data: ")) continue;
        const ev = JSON.parse(chunk.slice(6));
        if (ev.type === "session") chat.sessionId = ev.session_id;
        else if (ev.type === "text") appendText(turn, ev.text);
        else if (ev.type === "tool_call") {
          turn.bubble = null; turn.tools.push(ev.name);
          turn.steps.insertAdjacentHTML("beforeend", `<span class="step" data-id="${esc(ev.id)}"><span class="spin"></span>${esc(STEP_LABEL[ev.name] || ev.name)}</span>`);
          scrollDown();
        } else if (ev.type === "tool_result") {
          const el = turn.steps.querySelector(`[data-id="${CSS.escape(ev.id)}"]`);
          if (el) { el.classList.add(ev.is_error ? "err" : "done"); el.querySelector(".spin")?.replaceWith(document.createRange().createContextualFragment(ic(ev.is_error ? "alert" : "check"))); }
          if (ev.name === "render_card" && !ev.is_error && ev.result.image) addCard(turn, ev.result);
          else if (!ev.is_error) { const w = widgetFor(ev.name, ev.result); if (w) { turn.el.querySelector(".typing")?.remove(); turn.el.insertAdjacentHTML("beforeend", w); bindCards(turn.el); turn.bubble = null; scrollDown(); } }
        } else if (ev.type === "error") showError(turn, ev.message);
      }
    }
  } catch (e) { showError(turn, e.message || "연결이 끊겼어요. 다시 시도해 주세요."); }
  finally {
    turn.el.querySelector(".typing")?.remove();
    if (!turn.steps.children.length) turn.steps.remove();
    const f = [...new Set(turn.tools.flatMap((t) => FOLLOW[t] || []))].slice(0, 3);
    if (f.length) {
      turn.el.insertAdjacentHTML("beforeend", `<div class="follow">${f.map((x) => `<button>${esc(x)}</button>`).join("")}</div>`);
      turn.el.querySelectorAll(".follow button").forEach((b) => (b.onclick = () => send(b.textContent)));
    }
    chat.busy = false; $("#sendBtn").disabled = false; scrollDown();
  }
}
function autoGrow() { const i = $("#input"); i.style.height = "auto"; i.style.height = Math.min(i.scrollHeight, 160) + "px"; }
function clearAttach() { attached = null; $("#file").value = ""; $("#attachPreview").style.display = "none"; }

/* ================= 시작 ================= */
function init() {
  document.querySelectorAll("[data-ic]").forEach((el) => (el.innerHTML = ic(el.dataset.ic) + el.innerHTML));
  document.querySelectorAll(".seg button").forEach((b) => (b.onclick = () => { if (b.dataset.mode !== mode) setMode(b.dataset.mode); }));
  $("#fontBtn").onclick = () => {
    const on = document.body.classList.toggle("large"); $("#fontBtn").setAttribute("aria-pressed", String(on)); store.set("large", on);
    toast(on ? "글자를 크게 했어요" : "글자를 보통으로 했어요");
  };
  if (store.get("large", false)) { document.body.classList.add("large"); $("#fontBtn").setAttribute("aria-pressed", "true"); }
  $("#input").addEventListener("input", autoGrow);
  $("#input").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(); } });
  $("#form").addEventListener("submit", (e) => { e.preventDefault(); send(); });
  $("#attachBtn").onclick = () => $("#file").click();
  $("#file").onchange = (e) => {
    const f = e.target.files[0]; if (!f) return;
    if (f.size > 5 * 1024 * 1024) return toast("사진은 5MB 이하로 올려 주세요");
    attached = f;
    const p = $("#attachPreview"); p.querySelector("img").src = URL.createObjectURL(f); p.style.display = "flex";
    go("chat");
    if (pendingPhotoText) { $("#input").value = pendingPhotoText; pendingPhotoText = ""; }
    else if (!$("#input").value) $("#input").value = mode === "owner" ? "이 사진으로 메뉴판 만들어 주세요. 가게 이름은 " : "";
    $("#input").focus(); autoGrow();
  };
  $("#attachClear").onclick = (e) => { e.preventDefault(); clearAttach(); };
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SR) {
    const rec = new SR(); rec.lang = "ko-KR"; rec.interimResults = true; let on = false, base = "";
    $("#micBtn").hidden = false;
    $("#micBtn").onclick = () => { if (on) { rec.stop(); return; } base = $("#input").value; try { rec.start(); } catch {} };
    rec.onstart = () => { on = true; $("#micBtn").classList.add("on"); toast("말씀하세요"); };
    rec.onend = () => { on = false; $("#micBtn").classList.remove("on"); };
    rec.onresult = (e) => { $("#input").value = base + Array.from(e.results).map((r) => r[0].transcript).join(""); autoGrow(); };
  }
  if (!mode) { mode = "tourist"; renderNav(); go("home"); showOnboard(); }
  else { renderNav(); const t = location.hash.slice(1); go(TABS[mode].some(([id]) => id === t) ? t : TABS[mode][0][0]); }
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
}
init();
