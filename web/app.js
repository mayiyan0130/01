const LS_PROFILE = "jx_hub_profile_v1";
const LS_CUSTOM_NPCS = "jx_hub_custom_npcs_v1";
const LS_CHAT = "jx_hub_chat_v1";
const LS_FACTIONS = "jx_hub_factions_v2";

const STOCK_NPC = [
  { id: "stock-mo", configId: "mo_hongling", name: "莫红绫", blurb: "听风阁帮工 · 嘴硬心软" },
  { id: "stock-nangong", configId: "nangong_yi", name: "南宫翊", blurb: "微服皇子 · 少年意气" },
  { id: "stock-xie", configId: "xie_fuyao", name: "谢扶摇", blurb: "峨嵋大师姐 · 清正克制" },
  { id: "stock-jiang", configId: "jiang_lian", name: "江潋", blurb: "武林盟主 · 沉稳留白" },
  { id: "stock-yan", configId: "yan_wuqiu", name: "晏无秋", blurb: "拜月圣子 · 危险试探" },
];

/** 与 characters.json 对齐的兜底开场（无网或未拉到 brief 时使用） */
const STOCK_OPENINGS = {
  mo_hongling:
    "掌柜的，那些苍蝇已经打发走了，别总盯着窗外看，茶凉了……我可不帮你重泡。",
  nangong_yi:
    "掌柜的，你这儿可有百晓生最新的传闻？本皇……本公子重重有赏！真羡慕那百晓生，一扇一马便可走遍天涯。",
  xie_fuyao: "阁主，这支玉笛近日音色不稳，是否因这酒阁内湿气太重？您能否帮我看看。",
  jiang_lian: "这酒的味道……很像华山多年前的「雪中春」。掌柜，我们是否……曾在哪里见过？",
  yan_wuqiu: "有趣。一个小小的酒楼掌柜，竟然能藏住这么多有趣的事——你觉得，你能藏多久？",
};

const DEFAULT_FACTIONS = [
  { id: "huashan", name: "华山", power: 34 },
  { id: "wudang", name: "武当", power: 28 },
  { id: "emei", name: "峨嵋", power: 18 },
  { id: "yaowang", name: "药王谷", power: 20 },
  { id: "tangmen", name: "唐门", power: 16 },
  { id: "baiyue", name: "拜月", power: 28 },
  { id: "wudu", name: "五毒", power: 12 },
];

function readJSON(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function writeJSON(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function loadProfile() {
  const data = readJSON(LS_PROFILE, {});
  if (data.playerName) stateStore.playerName = data.playerName;
  if (data.playerGender) stateStore.playerGender = data.playerGender;
}

function saveProfile() {
  writeJSON(LS_PROFILE, { playerName: stateStore.playerName, playerGender: stateStore.playerGender });
}

function loadCustomNpcs() {
  const list = readJSON(LS_CUSTOM_NPCS, []);
  stateStore.customNpcs = Array.isArray(list) ? list : [];
}

function saveCustomNpcs() {
  writeJSON(LS_CUSTOM_NPCS, stateStore.customNpcs);
}

function loadChatStore() {
  stateStore.chatByContact = readJSON(LS_CHAT, {});
}

function saveChatStore() {
  writeJSON(LS_CHAT, stateStore.chatByContact);
}

function loadFactionStore() {
  const data = readJSON(LS_FACTIONS, null);
  stateStore.factions = Array.isArray(data) && data.length ? data : DEFAULT_FACTIONS.map((f) => ({ ...f }));
}

function saveFactionStore() {
  writeJSON(LS_FACTIONS, stateStore.factions);
}

const stateStore = {
  playerName: "言笑笑",
  playerGender: "female",
  gameState: null,
  currentScene: null,
  busy: false,
  pendingMiniGame: null,
  completedMiniGameResult: null,
  miniSession: null,
  snakeLoop: null,
  snakeTimer: null,
  match3Atlas: null,
  match3Swipe: null,
  suppressMatch3ClickUntil: 0,
  customNpcs: [],
  chatByContact: {},
  factions: DEFAULT_FACTIONS.map((f) => ({ ...f })),
  activeChatId: null,
  chatBusy: false,
  giftBusy: false,
  intelSellBusy: false,
  characterBriefById: {},
  characterBriefLoaded: false,
};

loadProfile();
loadCustomNpcs();
loadChatStore();
loadFactionStore();

const MATCH3_ATLAS_URL = "/static/assets/sanxiao/chapter01_match3_atlas.json";

const MATCH3_FALLBACK_TILES = [
  {
    id: "jiutan",
    code: "01",
    label: "玲珑酒坛",
    color: "linear-gradient(180deg, #d8b58e, #b96b46)",
    particleColor: "rgba(214, 161, 104, 0.92)",
  },
  {
    id: "peach_letter",
    code: "02",
    label: "桃花笺",
    color: "linear-gradient(180deg, #f2d3dd, #df9fb4)",
    particleColor: "rgba(243, 187, 205, 0.94)",
  },
  {
    id: "fox_mask",
    code: "04",
    label: "赤狐面具",
    color: "linear-gradient(180deg, #f09a79, #cb5447)",
    particleColor: "rgba(237, 136, 103, 0.94)",
  },
  {
    id: "gold_ingot",
    code: "05",
    label: "小金元宝",
    color: "linear-gradient(180deg, #f8db6d, #d79a20)",
    particleColor: "rgba(247, 214, 94, 0.96)",
  },
];

const MERGE_TILES = {
  0: { level: 0, code: "", label: "", color: "rgba(111, 67, 38, 0.08)" },
  1: {
    level: 1,
    code: "01",
    label: "飞舞的小纸条",
    color: "linear-gradient(180deg, #f6e7d8, #e6c6a9)",
    imageUrl: "/static/assets/erhe/erhe_01_flying_note.png",
  },
  2: {
    level: 2,
    code: "02",
    label: "听风铃铎",
    color: "linear-gradient(180deg, #f3dcc7, #d8a47b)",
    imageUrl: "/static/assets/erhe/erhe_02_wind_bell.png",
  },
  3: {
    level: 3,
    code: "03",
    label: "封蜡信笺",
    color: "linear-gradient(180deg, #f7e0df, #e0b6bd)",
    imageUrl: "/static/assets/erhe/erhe_03_sealed_letter.png",
  },
};

const el = {
  appShell: document.querySelector(".app-shell"),
  openingLobby: document.querySelector("#opening-lobby"),
  openingStartButton: document.querySelector("#opening-start-button"),
  openingLobbyError: document.querySelector("#opening-lobby-error"),
  sceneTitle: document.querySelector("#scene-title"),
  scenePhase: document.querySelector("#scene-phase"),
  storyEngine: document.querySelector("#story-engine"),
  storyScroll: document.querySelector("#story-scroll"),
  narration: document.querySelector("#narration"),
  dialogueList: document.querySelector("#dialogue-list"),
  stateCommentary: document.querySelector("#state-commentary"),
  silver: document.querySelector("#silver"),
  intel: document.querySelector("#intel"),
  exposure: document.querySelector("#exposure"),
  heat: document.querySelector("#heat"),
  rapportList: document.querySelector("#rapport-list"),
  choices: document.querySelector("#choices"),
  actionRow: document.querySelector(".action-row"),
  freeInputWrap: document.querySelector(".free-input"),
  freeInput: document.querySelector("#free-input"),
  freeSubmit: document.querySelector("#free-submit"),
  startButton: document.querySelector("#start-button"),
  restartButton: document.querySelector("#restart-button"),
  miniOverlay: document.querySelector("#mini-overlay"),
  closeMiniButton: document.querySelector("#close-mini-button"),
  miniGameTitle: document.querySelector("#mini-game-title"),
  miniShellCopy: document.querySelector("#mini-shell-copy"),
  miniStats: document.querySelector("#mini-stats"),
  miniNotice: document.querySelector("#mini-notice"),
  miniStage: document.querySelector("#mini-stage"),
  match3Board: document.querySelector("#match3-board"),
  mergeBoard: document.querySelector("#merge-board"),
  snakeWrap: document.querySelector("#snake-wrap"),
  snakeCanvas: document.querySelector("#snake-canvas"),
  miniFeedback: document.querySelector("#mini-feedback"),
  miniStartButton: document.querySelector("#mini-start-button"),
  miniSubmitButton: document.querySelector("#mini-submit-button"),
  dirButtons: document.querySelectorAll(".dir-button"),
  hubChat: document.querySelector("#hub-chat"),
  hubItems: document.querySelector("#hub-items"),
  hubFactions: document.querySelector("#hub-factions"),
  hubCustom: document.querySelector("#hub-custom"),
  hubChatOverlay: document.querySelector("#hub-chat-overlay"),
  hubItemsOverlay: document.querySelector("#hub-items-overlay"),
  hubFactionsOverlay: document.querySelector("#hub-factions-overlay"),
  hubCustomOverlay: document.querySelector("#hub-custom-overlay"),
  wechatClose: document.querySelector("#wechat-close"),
  wechatListScreen: document.querySelector("#wechat-list-screen"),
  wechatThreadScreen: document.querySelector("#wechat-thread-screen"),
  wechatBack: document.querySelector("#wechat-back"),
  wechatContactList: document.querySelector("#wechat-contact-list"),
  wechatMessages: document.querySelector("#wechat-messages"),
  wechatThreadTitle: document.querySelector("#wechat-thread-title"),
  wechatInput: document.querySelector("#wechat-input"),
  wechatSend: document.querySelector("#wechat-send"),
  wechatGift: document.querySelector("#wechat-gift"),
  giftPicker: document.querySelector("#gift-picker"),
  giftPickerList: document.querySelector("#gift-picker-list"),
  giftPickerClose: document.querySelector("#gift-picker-close"),
  intelItemList: document.querySelector("#intel-item-list"),
  intelSaleFeedback: document.querySelector("#intel-sale-feedback"),
  intelDetailOverlay: document.querySelector("#intel-detail-overlay"),
  intelDetailTitle: document.querySelector("#intel-detail-title"),
  intelDetailTier: document.querySelector("#intel-detail-tier"),
  intelDetailBody: document.querySelector("#intel-detail-body"),
  intelDetailClose: document.querySelector("#intel-detail-close"),
  intelDetailSell: document.querySelector("#intel-detail-sell"),
  factionBars: document.querySelector("#faction-bars"),
  factionLeaderNote: document.querySelector("#faction-leader-note"),
  customPlayerName: document.querySelector("#custom-player-name"),
  customNpcName: document.querySelector("#custom-npc-name"),
  customNpcPersonality: document.querySelector("#custom-npc-personality"),
  customNpcBackstory: document.querySelector("#custom-npc-backstory"),
  customSavePlayer: document.querySelector("#custom-save-player"),
  customAddNpc: document.querySelector("#custom-add-npc"),
};

const dialogueTemplate = document.querySelector("#dialogue-template");
const choiceTemplate = document.querySelector("#choice-template");

async function loadMatch3Atlas() {
  if (stateStore.match3Atlas) return stateStore.match3Atlas;

  try {
    const response = await fetch(MATCH3_ATLAS_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const atlas = await response.json();
    atlas.imageUrl = atlas.meta?.imagePath || "/static/assets/sanxiao/chapter01_match3_atlas.png";
    stateStore.match3Atlas = atlas;
  } catch (error) {
    console.warn("Match3 atlas unavailable, fallback to coded tiles.", error);
    stateStore.match3Atlas = null;
  }

  return stateStore.match3Atlas;
}

function getMatch3Tiles() {
  const atlas = stateStore.match3Atlas;
  if (!atlas?.tileOrder?.length || !atlas?.frames) return MATCH3_FALLBACK_TILES;

  return atlas.tileOrder.map((id, index) => {
    const frame = atlas.frames[id] || {};
    return {
      id,
      code: frame.code || String(index + 1).padStart(2, "0"),
      label: frame.label || id,
      atlasFrame: frame,
      color: MATCH3_FALLBACK_TILES[index % MATCH3_FALLBACK_TILES.length].color,
      particleColor: MATCH3_FALLBACK_TILES[index % MATCH3_FALLBACK_TILES.length].particleColor,
    };
  });
}

function getMatch3LegendText() {
  return getMatch3Tiles()
    .map((tile) => `${tile.code} ${tile.label}`)
    .join(" / ");
}

function getMatch3StatBadges(session) {
  return [
    "第一关宽松开局",
    `投放元素 ${getMatch3Tiles().map((tile) => tile.code).join("/")}`,
    `目标消除 ${session.target}`,
    `剩余步数 ${session.moves}`,
    `已消除 ${session.cleared}`,
  ];
}

function ensureQuotedLine(text = "") {
  const trimmed = text.trim();
  if (!trimmed) return "“……”";
  if (/^[“"「『]/.test(trimmed)) return trimmed;
  return `“${trimmed}”`;
}

function formatNarrationBlock(payload) {
  const loc = (payload.location || "听风阁").trim();
  const lines = [`*地点：${loc}*`, "", payload.narration || ""];
  return lines.join("\n").trim();
}

function formatStateCommentaryBlock(payload) {
  const lines = [];
  if (payload.state_commentary) lines.push(`*局面提醒：${payload.state_commentary.trim()}*`);
  return lines.join("\n");
}

function applyMatch3TileAppearance(node, tileData) {
  node.innerHTML = "";
  node.style.background = tileData.color;
  node.setAttribute("aria-label", `${tileData.code} ${tileData.label}`);

  const atlas = stateStore.match3Atlas;
  const atlasFrame = tileData.atlasFrame;
  if (atlas?.meta?.size && atlasFrame?.frame) {
    const icon = document.createElement("span");
    icon.className = "match3-icon";

    const sprite = document.createElement("span");
    sprite.className = "match3-sprite";
    sprite.style.width = `${atlasFrame.frame.w}px`;
    sprite.style.height = `${atlasFrame.frame.h}px`;
    sprite.style.backgroundImage = `url(${atlas.imageUrl})`;
    sprite.style.backgroundSize = `${atlas.meta.size.w}px ${atlas.meta.size.h}px`;
    sprite.style.backgroundPosition = `-${atlasFrame.frame.x}px -${atlasFrame.frame.y}px`;
    sprite.style.transform = `scale(${40 / atlasFrame.frame.w})`;
    icon.appendChild(sprite);
    node.appendChild(icon);
  } else {
    const fallbackCode = document.createElement("span");
    fallbackCode.className = "match3-code only-code";
    fallbackCode.textContent = tileData.code;
    node.appendChild(fallbackCode);
  }

  const codeBadge = document.createElement("span");
  codeBadge.className = "match3-code";
  codeBadge.textContent = tileData.code;
  node.appendChild(codeBadge);
}

function setBusy(nextBusy) {
  stateStore.busy = nextBusy;
  document.body.classList.toggle("loading", nextBusy);
  [
    el.openingStartButton,
    el.freeSubmit,
    el.startButton,
    el.restartButton,
    el.freeInput,
    el.closeMiniButton,
    el.miniStartButton,
    el.miniSubmitButton,
  ].forEach((node) => {
    if (!node) return;
    node.disabled = nextBusy;
    node.classList.toggle("is-busy", nextBusy);
  });
  Array.from(el.choices.querySelectorAll("button")).forEach((button) => {
    button.disabled = nextBusy;
    button.classList.toggle("is-busy", nextBusy);
  });
}

function clearOpeningLobbyError() {
  if (!el.openingLobbyError) return;
  el.openingLobbyError.textContent = "";
  el.openingLobbyError.classList.add("hidden");
}

function showOpeningLobbyError(message) {
  if (!el.openingLobbyError) return;
  el.openingLobbyError.textContent = message;
  el.openingLobbyError.classList.remove("hidden");
}

function playOpeningStartPressFx() {
  if (!el.openingStartButton) return Promise.resolve();
  el.openingStartButton.classList.remove("is-pressing");
  // Restart the press animation so each click gets one clear pulse.
  void el.openingStartButton.offsetWidth;
  el.openingStartButton.classList.add("is-pressing");
  return new Promise((resolve) => {
    window.setTimeout(() => {
      el.openingStartButton?.classList.remove("is-pressing");
      resolve();
    }, 220);
  });
}

function clearSnakeLoops() {
  if (stateStore.snakeLoop) {
    clearInterval(stateStore.snakeLoop);
    stateStore.snakeLoop = null;
  }
  if (stateStore.snakeTimer) {
    clearInterval(stateStore.snakeTimer);
    stateStore.snakeTimer = null;
  }
}

function renderDialogue(dialogue = []) {
  el.dialogueList.innerHTML = "";
  dialogue.forEach((item) => {
    const fragment = dialogueTemplate.content.cloneNode(true);
    fragment.querySelector(".speaker").textContent = `*${item.speaker || "旁白"}`;
    fragment.querySelector(".mood").textContent = item.mood ? ` · ${item.mood}*` : "*";
    fragment.querySelector(".line").textContent = ensureQuotedLine(item.text || "");
    el.dialogueList.appendChild(fragment);
  });
}

function renderChoices(choices = []) {
  el.choices.innerHTML = "";
  choices.forEach((choice) => {
    const fragment = choiceTemplate.content.cloneNode(true);
    const button = fragment.querySelector(".choice-button");
    button.querySelector(".choice-label").textContent = choice.label;
    button.querySelector(".choice-risk").textContent = choice.risk_hint || "无风险提示";
    button.addEventListener("click", () => advanceScene(choice));
    el.choices.appendChild(fragment);
  });
}

function mergeRapportForDisplay(rapport = {}) {
  const merged = { ...rapport };
  stateStore.customNpcs.forEach((npc) => {
    if (!(npc.name in merged)) merged[npc.name] = 8;
  });
  return merged;
}

function renderRapport(rapport = {}) {
  el.rapportList.innerHTML = "";
  const merged = mergeRapportForDisplay(rapport);
  Object.entries(merged).forEach(([name, value]) => {
    const card = document.createElement("article");
    card.className = "status-bar-item";
    const safeValue = Math.max(0, Math.min(100, Number(value) || 0));
    card.innerHTML = `
      <div class="status-bar-copy">
        <strong>${escapeHtml(name)}</strong>
        <span class="status-bar-value">${escapeHtml(String(safeValue))}</span>
      </div>
      <div class="status-bar-track">
        <div class="status-bar-fill" style="width:${safeValue}%"></div>
      </div>
    `;
    el.rapportList.appendChild(card);
  });
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function getAllContacts() {
  const custom = stateStore.customNpcs.map((npc) => ({
    id: npc.id,
    name: npc.name,
    blurb: `${npc.personality || "自定义"} · ${(npc.backstory || "").slice(0, 24)}`,
    isCustom: true,
  }));
  const stock = STOCK_NPC.map((s) => ({ ...s, isCustom: false }));
  return [...stock, ...custom];
}

function getContactMeta(id) {
  return getAllContacts().find((c) => c.id === id);
}

function getContactBrief(contact) {
  if (!contact?.configId) return null;
  return stateStore.characterBriefById[contact.configId] || null;
}

/** @returns {string|null} 锁定原因文案；null 表示可点入 */
function contactPrivateLockMessage(contact) {
  if (contact.isCustom) return null;
  if (!stateStore.gameState) return "开章后在主线中与此人照面，方可传信。";
  const met = stateStore.gameState.met_npc_config_ids || [];
  if (!met.includes(contact.configId)) return "剧情未与此人照面，传信未通。";
  return null;
}

async function ensureCharacterBriefs() {
  if (stateStore.characterBriefLoaded) return;
  try {
    const response = await fetch("/api/hub/character_brief");
    if (!response.ok) throw new Error("brief");
    const data = await response.json();
    const map = {};
    (data.characters || []).forEach((c) => {
      if (c && c.id) map[c.id] = c;
    });
    stateStore.characterBriefById = map;
  } catch {
    stateStore.characterBriefById = stateStore.characterBriefById || {};
  }
  stateStore.characterBriefLoaded = true;
}

function buildAvatarElement(contact, side) {
  const wrap = document.createElement("div");
  wrap.className = `wechat-avatar wechat-avatar--round wechat-avatar--${side}`;
  const initial = (contact?.name || stateStore.playerName || "?").slice(0, 1);
  const brief = contact && !contact.isCustom ? getContactBrief(contact) : null;
  const url = (brief?.avatar_url || "").trim();
  if (url) {
    const img = document.createElement("img");
    img.className = "wechat-avatar-img";
    img.src = url;
    img.alt = "";
    img.referrerPolicy = "no-referrer";
    img.addEventListener("error", () => {
      img.remove();
      wrap.textContent = initial;
    });
    wrap.appendChild(img);
  } else {
    wrap.textContent = initial;
  }
  return wrap;
}

function openingLineForContact(contact) {
  if (contact.isCustom) {
    return `我是${contact.name}。${stateStore.customNpcs.find((n) => n.id === contact.id)?.backstory || "往后请多指教。"}`;
  }
  const fromBrief = getContactBrief(contact)?.chat_opening;
  if (fromBrief) return fromBrief;
  return STOCK_OPENINGS[contact.configId] || `（${contact.name}）阁里眼杂，长话短说。`;
}

function chatKeyForContact(contact) {
  return contact.isCustom ? contact.id : contact.name;
}

function lastPreviewForContact(contact) {
  const key = chatKeyForContact(contact);
  const rows = stateStore.chatByContact[key];
  if (rows?.length) return rows[rows.length - 1].text;
  return contact.blurb || "点此传信";
}

function renderWechatContacts() {
  el.wechatContactList.innerHTML = "";
  getAllContacts().forEach((contact) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "wechat-row";
    const lockMsg = contactPrivateLockMessage(contact);
    const locked = Boolean(lockMsg);
    if (locked) {
      row.disabled = true;
      row.style.opacity = "0.5";
    }
    const av = buildAvatarElement(contact, "list");
    row.appendChild(av);
    const main = document.createElement("span");
    main.className = "wechat-row-main";
    const nameEl = document.createElement("span");
    nameEl.className = "wechat-row-name";
    nameEl.textContent = contact.name;
    const previewEl = document.createElement("span");
    previewEl.className = "wechat-row-preview";
    previewEl.textContent = locked ? lockMsg : lastPreviewForContact(contact);
    main.appendChild(nameEl);
    main.appendChild(previewEl);
    const badge = document.createElement("span");
    badge.className = "wechat-badge";
    badge.textContent = contact.isCustom ? "自定义" : "江湖";
    row.appendChild(main);
    row.appendChild(badge);
    if (!locked) {
      row.addEventListener("click", () => void openWechatThread(contact.id));
    }
    el.wechatContactList.appendChild(row);
  });
}

function seedNpcOpening(contact) {
  const key = chatKeyForContact(contact);
  if (stateStore.chatByContact[key]?.length) return;
  const opening = openingLineForContact(contact);
  stateStore.chatByContact[key] = [{ from: "them", text: opening, ts: Date.now() }];
  saveChatStore();
}

async function openWechatThread(contactId) {
  const contact = getContactMeta(contactId);
  if (!contact) return;
  if (contactPrivateLockMessage(contact)) return;
  await ensureCharacterBriefs();
  stateStore.activeChatId = contactId;
  seedNpcOpening(contact);
  el.wechatListScreen.classList.add("hidden");
  el.wechatThreadScreen.classList.remove("hidden");
  el.wechatThreadTitle.textContent = contact.name;
  if (el.wechatGift) {
    el.wechatGift.classList.toggle("hidden", Boolean(contact.isCustom));
    el.wechatGift.disabled = !stateStore.gameState || Boolean(contact.isCustom);
  }
  renderWechatMessages(contact);
  el.wechatInput.value = "";
  el.wechatInput.focus();
}

function renderWechatMessages(contact) {
  const key = chatKeyForContact(contact);
  const rows = stateStore.chatByContact[key] || [];
  el.wechatMessages.innerHTML = "";
  const npcBubbleContact = contact.isCustom ? contact : contact;
  rows.forEach((row) => {
    const line = document.createElement("div");
    const isMe = row.from === "me";
    line.className = `wechat-msg-row ${isMe ? "wechat-msg-row--me" : "wechat-msg-row--them"}`;
    const av = buildAvatarElement(isMe ? { name: stateStore.playerName, isCustom: true } : npcBubbleContact, isMe ? "me" : "them");
    const bubble = document.createElement("div");
    bubble.className = `wechat-bubble ${isMe ? "me" : "them"}`;
    bubble.textContent = row.text;
    if (isMe) {
      line.appendChild(bubble);
      line.appendChild(av);
    } else {
      line.appendChild(av);
      line.appendChild(bubble);
    }
    el.wechatMessages.appendChild(line);
  });
  el.wechatMessages.scrollTop = el.wechatMessages.scrollHeight;
}

function pushChatMessage(contact, from, text) {
  const key = chatKeyForContact(contact);
  if (!stateStore.chatByContact[key]) stateStore.chatByContact[key] = [];
  stateStore.chatByContact[key].push({ from, text, ts: Date.now() });
  saveChatStore();
}

function npcAutoReply(contact, playerText) {
  if (contact.isCustom) {
    const npc = stateStore.customNpcs.find((n) => n.id === contact.id);
    const p = npc?.personality || "寡言";
    return `（${contact.name}）你说的事我记下了。以我性子——${p}——改日当面再谈更妥。`;
  }
  const fallbacks = [
    `（${contact.name}）这话在阁里说不便，我记下了。`,
    `（${contact.name}）先按你说的办，外头耳目多。`,
    `（${contact.name}）嗯。你稳住，别露底。`,
  ];
  return fallbacks[Math.floor(Math.random() * fallbacks.length)];
}

function buildStoryContext() {
  const s = stateStore.currentScene;
  if (!s) return {};
  return {
    scene_title: s.scene_title,
    scene_phase: s.scene_phase,
    beat_summary: s.beat_summary,
    focus_npc: s.focus_npc,
    state_commentary: s.state_commentary,
  };
}

function mergeGameStateFromHub(next) {
  if (!next || typeof next !== "object") return;
  stateStore.gameState = next;
  if (stateStore.currentScene) {
    stateStore.currentScene = { ...stateStore.currentScene, state: next };
  }
  if (el.silver) el.silver.textContent = next.silver;
  if (el.intel) el.intel.textContent = next.intel;
  if (el.exposure) el.exposure.textContent = next.exposure;
  if (el.heat) el.heat.textContent = next.tavern_heat;
  renderRapport(next.rapport || {});
}

function closeGiftPicker() {
  if (!el.giftPicker) return;
  el.giftPicker.classList.add("hidden");
  el.giftPicker.setAttribute("aria-hidden", "true");
}

function openGiftPicker() {
  const contact = getContactMeta(stateStore.activeChatId);
  if (!contact || contact.isCustom || !stateStore.gameState) return;
  if (contactPrivateLockMessage(contact)) return;
  if (!el.giftPicker || !el.giftPickerList) return;
  const gifts = Array.isArray(stateStore.gameState.player_merge_gifts)
    ? [...stateStore.gameState.player_merge_gifts]
    : [];
  el.giftPickerList.innerHTML = "";
  if (!gifts.length) {
    const li = document.createElement("li");
    li.className = "gift-picker-empty";
    li.textContent = "暂无信物。完成二合整编后可得裁光纸条、桃花笺、青竹笛等。";
    el.giftPickerList.appendChild(li);
  } else {
    gifts.forEach((label) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "gift-picker-item";
      btn.textContent = label;
      btn.addEventListener("click", () => void submitPrivateGift(contact, label));
      li.appendChild(btn);
      el.giftPickerList.appendChild(li);
    });
  }
  el.giftPicker.classList.remove("hidden");
  el.giftPicker.setAttribute("aria-hidden", "false");
}

async function submitPrivateGift(contact, giftLabel) {
  if (stateStore.giftBusy || !stateStore.gameState || contact.isCustom) return;
  stateStore.giftBusy = true;
  closeGiftPicker();
  try {
    const data = await requestJSON("/api/hub/private_gift", {
      player_name: stateStore.playerName,
      player_gender: stateStore.playerGender,
      state: stateStore.gameState,
      character_config_id: contact.configId,
      gift_label: giftLabel,
    });
    mergeGameStateFromHub(data.state);
    const reply = (data.reply || "").trim() || "……收下了。";
    pushChatMessage(contact, "them", reply);
    renderWechatMessages(contact);
    renderWechatContacts();
  } catch (err) {
    pushChatMessage(contact, "them", `（未能递上此物：${err.message || err}）`);
    renderWechatMessages(contact);
  } finally {
    stateStore.giftBusy = false;
  }
}

async function sendWechatMessage() {
  const contactId = stateStore.activeChatId;
  const contact = getContactMeta(contactId);
  if (!contact) return;
  const text = el.wechatInput.value.trim();
  if (!text) return;
  if (stateStore.chatBusy) return;

  pushChatMessage(contact, "me", text);
  el.wechatInput.value = "";
  renderWechatMessages(contact);

  const key = chatKeyForContact(contact);
  const thread = stateStore.chatByContact[key] || [];
  const history = thread.slice(0, -1).map((row) => ({
    role: row.from === "me" ? "user" : "assistant",
    content: row.text,
  }));

  stateStore.chatBusy = true;
  el.wechatSend.disabled = true;

  try {
    const body = {
      player_name: stateStore.playerName,
      player_gender: stateStore.playerGender,
      story_context: buildStoryContext(),
      history,
      message: text,
    };
    if (stateStore.gameState) {
      body.state = stateStore.gameState;
    }
    if (contact.isCustom) {
      const npc = stateStore.customNpcs.find((n) => n.id === contact.id);
      body.custom_npc = npc
        ? { name: npc.name, personality: npc.personality || "", backstory: npc.backstory || "" }
        : { name: contact.name, personality: "", backstory: "" };
    } else {
      body.character_config_id = contact.configId;
    }

    const response = await fetch("/api/hub/private_reply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    if (data.state) {
      mergeGameStateFromHub(data.state);
    }
    const reply = (data.reply || "").trim() || npcAutoReply(contact, text);
    pushChatMessage(contact, "them", reply);
  } catch {
    pushChatMessage(contact, "them", npcAutoReply(contact, text));
  } finally {
    stateStore.chatBusy = false;
    el.wechatSend.disabled = false;
    renderWechatMessages(contact);
    renderWechatContacts();
  }
}

function showWechatHome() {
  closeGiftPicker();
  el.wechatThreadScreen.classList.add("hidden");
  el.wechatListScreen.classList.remove("hidden");
  stateStore.activeChatId = null;
  renderWechatContacts();
}

function closeIntelDetailModal() {
  if (!el.intelDetailOverlay) return;
  el.intelDetailOverlay.classList.add("hidden");
  el.intelDetailOverlay.setAttribute("aria-hidden", "true");
}

function closeHubOverlays() {
  closeGiftPicker();
  closeIntelDetailModal();
  [el.hubChatOverlay, el.hubItemsOverlay, el.hubFactionsOverlay, el.hubCustomOverlay].forEach((node) => {
    if (!node) return;
    node.classList.add("hidden");
    node.setAttribute("aria-hidden", "true");
  });
  showWechatHome();
}

function openHubOverlay(which) {
  closeHubOverlays();
  const map = {
    chat: el.hubChatOverlay,
    items: el.hubItemsOverlay,
    factions: el.hubFactionsOverlay,
    custom: el.hubCustomOverlay,
  };
  const node = map[which];
  if (!node) return;
  node.classList.remove("hidden");
  node.setAttribute("aria-hidden", "false");
  if (which === "chat") {
    showWechatHome();
    void ensureCharacterBriefs().then(() => renderWechatContacts());
  }
  if (which === "items") {
    showIntelSaleFeedback("");
    closeIntelDetailModal();
    renderIntelPanel();
  }
  if (which === "factions") renderFactionPanel();
  if (which === "custom") syncCustomForm();
}

function syncCustomForm() {
  el.customPlayerName.value = stateStore.playerName;
  el.customNpcName.value = "";
  el.customNpcPersonality.value = "";
  el.customNpcBackstory.value = "";
}

/** 仅展示服务端已标为 merged_secret 的道具（与 STORY_LOG 等分离） */
function filterMergedForUI(secrets) {
  if (!Array.isArray(secrets)) return [];
  return secrets.filter((s) => {
    if (!s || s.secret_type !== "merged_secret") return false;
    const t = String(s.title || "").trim();
    if (t.length < 2) return false;
    if (/^(玩家|言笑|言笑笑)/.test(t)) return false;
    return true;
  });
}

function intelTierClass(tier) {
  const t = Number(tier);
  const n = Number.isFinite(t) ? Math.min(6, Math.max(1, Math.floor(t))) : 1;
  return `intel-card--tier-${n}`;
}

function renderIntelPanel() {
  el.intelItemList.innerHTML = "";
  const items = filterMergedForUI(stateStore.gameState?.player_secrets);
  if (!items.length) {
    const li = document.createElement("li");
    li.className = "empty-hint";
    li.textContent =
      "暂无秘辛。完成开局「二合」可解锁名录类 MERGED 情报；关键对白触发的条目也会出现在此（已自动剔除剧情进度描述）。";
    el.intelItemList.appendChild(li);
    return;
  }
  items.forEach((sec) => {
    const li = document.createElement("li");
    const tier = sec.tier != null ? Number(sec.tier) : 1;
    li.className = `intel-card ${intelTierClass(tier)}`;
    li.dataset.secretId = sec.id;
    const title = document.createElement("span");
    title.className = "intel-card-title";
    title.textContent = sec.title;
    const meta = document.createElement("span");
    meta.className = "intel-card-meta";
    meta.textContent = `Lv.${tier}`;
    li.appendChild(title);
    li.appendChild(meta);
    li.addEventListener("click", () => openIntelDetailModal(sec.id));
    el.intelItemList.appendChild(li);
  });
}

function mergeIntelFromScene(payload) {
  void payload;
}

async function openIntelDetailModal(secretId) {
  if (!stateStore.gameState || !el.intelDetailOverlay) return;
  el.intelDetailOverlay.classList.remove("hidden");
  el.intelDetailOverlay.setAttribute("aria-hidden", "false");
  el.intelDetailBody.textContent = "载入中…";
  el.intelDetailTitle.textContent = "秘辛";
  el.intelDetailTier.textContent = "";
  try {
    const data = await requestJSON("/api/hub/secret_detail", {
      player_name: stateStore.playerName,
      state: stateStore.gameState,
      secret_id: secretId,
    });
    stateStore.gameState = data.state;
    if (stateStore.currentScene) {
      stateStore.currentScene = { ...stateStore.currentScene, state: data.state };
    }
    el.intelDetailTitle.textContent = data.title;
    el.intelDetailTier.textContent = `情报等级 Lv.${data.tier}`;
    el.intelDetailBody.textContent = data.body;
    el.intelDetailOverlay.dataset.activeSecret = secretId;
  } catch (err) {
    el.intelDetailBody.textContent = `载入失败：${err.message || err}`;
  }
}

function syncSectFromState(gs) {
  const si = gs?.sect_influence;
  if (!si || typeof si !== "object") return;
  stateStore.factions = DEFAULT_FACTIONS.map((f) => {
    const p = si[f.name];
    return { ...f, power: typeof p === "number" ? p : f.power };
  });
  saveFactionStore();
}

function showIntelSaleFeedback(text) {
  if (!el.intelSaleFeedback) return;
  const msg = (text || "").trim();
  el.intelSaleFeedback.textContent = msg;
  el.intelSaleFeedback.classList.toggle("hidden", !msg);
}

async function sellIntelFromDetail(secretId) {
  if (!stateStore.gameState) {
    showIntelSaleFeedback("请先开章，再售卖情报。");
    return;
  }
  if (stateStore.intelSellBusy) return;
  const buyer = window.prompt(
    "售卖给哪一派？（华山、武当、峨嵋、药王谷、唐门、拜月、五毒）",
    "拜月",
  );
  if (buyer == null || !String(buyer).trim()) {
    showIntelSaleFeedback("");
    return;
  }
  const buyerSect = String(buyer).trim();
  stateStore.intelSellBusy = true;
  if (el.intelDetailSell) el.intelDetailSell.disabled = true;
  showIntelSaleFeedback("估价中…");
  try {
    const data = await requestJSON("/api/hub/sell_intel", {
      player_name: stateStore.playerName,
      state: stateStore.gameState,
      secret_id: secretId,
      buyer_sect: buyerSect,
    });
    stateStore.gameState = data.state;
    syncSectFromState(data.state);
    if (stateStore.currentScene) {
      stateStore.currentScene = { ...stateStore.currentScene, state: data.state };
    }
    el.silver.textContent = data.state.silver;
    el.intel.textContent = data.state.intel;
    el.exposure.textContent = data.state.exposure;
    renderRapport(data.state.rapport);
    const tier = data.value_tier || "中";
    const sectLabel = data.buyer_sect || buyerSect;
    showIntelSaleFeedback(
      `「${tier}」价 ${data.silver_delta >= 0 ? "+" : ""}${data.silver_delta} 银两；${sectLabel} 声势 ${data.buyer_influence_delta >= 0 ? "+" : ""}${data.buyer_influence_delta}；暴露 ${data.exposure_delta >= 0 ? "+" : ""}${data.exposure_delta}。${data.verdict || ""}`,
    );
    closeIntelDetailModal();
    renderIntelPanel();
    renderFactionPanel();
  } catch (err) {
    showIntelSaleFeedback(`售卖失败：${err.message || err}`);
  } finally {
    stateStore.intelSellBusy = false;
    if (el.intelDetailSell) el.intelDetailSell.disabled = false;
  }
}

function renderFactionPanel() {
  el.factionBars.innerHTML = "";
  const sorted = [...stateStore.factions].sort((a, b) => b.power - a.power);
  sorted.forEach((f) => {
    const row = document.createElement("div");
    row.className = "faction-row";
    row.innerHTML = `
      <header>
        <strong>${escapeHtml(f.name)}</strong>
        <span>${f.power}/100</span>
      </header>
      <div class="faction-bar">
        <div class="faction-fill" style="width:${Math.min(100, f.power)}%"></div>
      </div>
    `;
    el.factionBars.appendChild(row);
  });
  const at100 = stateStore.factions.find((f) => f.power >= 100);
  el.factionLeaderNote.textContent = at100
    ? `「${at100.name}」势力已达巅峰，江湖公议将推举武林盟主（试玩展示）。`
    : "局势仍在胶着，继续经营听风阁以撬动各派声势。";
}

function syncActionPanel() {
  const hasStarted = Boolean(stateStore.gameState);
  el.appShell?.classList.toggle("app-shell--lobby", !hasStarted);
  el.choices.classList.toggle("hidden", !hasStarted);
  el.freeInputWrap.classList.toggle("hidden", !hasStarted);
  el.freeSubmit.classList.toggle("hidden", !hasStarted);
  el.restartButton.classList.toggle("hidden", !hasStarted);
  el.startButton.classList.toggle("hidden", hasStarted);
  el.actionRow.classList.toggle("single-button", true);
  if (hasStarted) clearOpeningLobbyError();
}

function setMiniFeedback(text) {
  el.miniFeedback.textContent = text;
}

function renderMiniStats(items = []) {
  el.miniStats.innerHTML = "";
  items.forEach((item) => {
    const badge = document.createElement("span");
    badge.className = "mini-stat";
    badge.textContent = item;
    el.miniStats.appendChild(badge);
  });
}

function setMiniNotice(text = "", tone = "alert") {
  el.miniNotice.textContent = text;
  el.miniNotice.classList.toggle("hidden", !text);
  el.miniNotice.dataset.tone = tone;
}

function resetMiniStage() {
  clearSnakeLoops();
  stateStore.miniSession = null;
  stateStore.completedMiniGameResult = null;
  setMiniNotice("");
  el.match3Board.classList.add("hidden");
  el.mergeBoard.classList.add("hidden");
  el.snakeWrap.classList.add("hidden");
  el.miniSubmitButton.classList.add("hidden");
  el.miniStartButton.classList.remove("hidden");
}

function openMiniOverlay() {
  if (!stateStore.pendingMiniGame) return;
  el.miniOverlay.classList.remove("hidden");
  el.miniOverlay.setAttribute("aria-hidden", "false");
}

function closeMiniOverlay() {
  clearSnakeLoops();
  el.miniOverlay.classList.add("hidden");
  el.miniOverlay.setAttribute("aria-hidden", "true");
}

function prepareMiniGame(miniGame) {
  stateStore.pendingMiniGame = miniGame.type === "none" ? null : miniGame;
  if (!stateStore.pendingMiniGame) {
    closeMiniOverlay();
    return;
  }

  resetMiniStage();
  el.miniGameTitle.textContent = {
    match3: "第一章三消 · 听风阁夜局",
    merge: "第一章二合 · 风声整编",
    snake: "贪吃蛇 · 追索风声",
  }[miniGame.type];
  el.miniShellCopy.textContent = `${miniGame.reason} ${miniGame.stakes}`;
  renderMiniStats(
    miniGame.type === "match3"
      ? ["第一关宽松开局", "投放元素 01/02/04/05", "滑动交换并看下落连消"]
      : miniGame.type === "merge"
        ? ["开局试玩", "仅启用素材 01/02/03", "合成到 03 即可接入剧情"]
        : ["难度已下调", "吃到 2 个即可过关", "方向键或按钮都能操作"],
  );
  setMiniFeedback("准备完成后点击“开始挑战”。");
  openMiniOverlay();
}

function renderScene(payload) {
  stateStore.currentScene = payload;
  stateStore.gameState = payload.state;

  el.sceneTitle.textContent = payload.scene_title;
  el.scenePhase.textContent = payload.scene_phase;
  if (el.storyEngine) {
    el.storyEngine.textContent = payload.using_fallback ? "本轮改用本地兜底" : "AI 正在续写";
    el.storyEngine.dataset.mode = payload.using_fallback ? "fallback" : "live";
  }
  el.narration.textContent = formatNarrationBlock(payload);
  el.stateCommentary.textContent = formatStateCommentaryBlock(payload);
  el.silver.textContent = payload.state.silver;
  el.intel.textContent = payload.state.intel;
  el.exposure.textContent = payload.state.exposure;
  el.heat.textContent = payload.state.tavern_heat;

  renderDialogue(payload.dialogue);
  renderChoices(payload.choices);
  renderRapport(payload.state.rapport);
  mergeIntelFromScene(payload);
  syncSectFromState(payload.state);
  renderFactionPanel();
  prepareMiniGame(payload.mini_game);
  syncActionPanel();
  if (el.hubChatOverlay && !el.hubChatOverlay.classList.contains("hidden")) {
    renderWechatContacts();
  }
  if (el.storyScroll) el.storyScroll.scrollTop = 0;
}

async function requestJSON(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `HTTP ${response.status}`);
  }
  return response.json();
}

async function startChapter(options = {}) {
  const autoStartOpeningMerge = options.autoStartOpeningMerge !== false;
  resetMiniStage();
  closeMiniOverlay();
  el.appShell?.removeAttribute("data-lobby-error");
  clearOpeningLobbyError();
  await playOpeningStartPressFx();
  el.openingStartButton?.classList.add("is-loading");
  setBusy(true);
  try {
    const payload = await requestJSON("/api/chapter/start", {
      player_name: stateStore.playerName,
      player_gender: stateStore.playerGender,
    });
    renderScene(payload);
    el.freeInput.value = "";
    if (autoStartOpeningMerge && stateStore.pendingMiniGame?.type === "merge") {
      await startMiniGame();
    }
  } catch (error) {
    el.appShell?.setAttribute("data-lobby-error", "1");
    const msg = `开章失败：${error.message}`;
    el.narration.textContent = msg;
    el.stateCommentary.textContent = msg;
    showOpeningLobbyError(msg);
  } finally {
    setBusy(false);
    el.openingStartButton?.classList.remove("is-loading");
  }
}

async function advanceScene(choice = null) {
  if (!stateStore.gameState) {
    await startChapter();
    return;
  }

  const playerInput = el.freeInput.value.trim();
  setBusy(true);
  try {
    const payload = await requestJSON("/api/chapter/advance", {
      player_name: stateStore.playerName,
      player_gender: stateStore.playerGender,
      state: stateStore.gameState,
      choice,
      player_input: playerInput,
    });
    renderScene(payload);
    el.freeInput.value = "";
  } catch (error) {
    el.stateCommentary.textContent = `续写失败：${error.message}`;
  } finally {
    setBusy(false);
  }
}

async function submitMiniGameResult() {
  if (!stateStore.completedMiniGameResult || !stateStore.gameState) return;

  setBusy(true);
  try {
    const payload = await requestJSON("/api/chapter/minigame", {
      player_name: stateStore.playerName,
      player_gender: stateStore.playerGender,
      state: stateStore.gameState,
      result: stateStore.completedMiniGameResult,
    });
    closeMiniOverlay();
    renderScene(payload);
  } catch (error) {
    setMiniFeedback(`小游戏结算失败：${error.message}`);
  } finally {
    setBusy(false);
  }
}

function finishMiniGame(success, score, summary, details = {}) {
  if (!stateStore.pendingMiniGame) return;
  clearSnakeLoops();
  stateStore.completedMiniGameResult = {
    type: stateStore.pendingMiniGame.type,
    success,
    score,
    summary,
    ...details,
  };
  const verdict = success ? "成功" : "失败";
  setMiniFeedback(`${verdict}。${summary}`);
  el.miniSubmitButton.classList.remove("hidden");
  el.miniStartButton.classList.add("hidden");
}

function createBaseBoard(size, symbolCount) {
  const board = Array(size * size).fill(0);
  for (let index = 0; index < board.length; index += 1) {
    let next = Math.floor(Math.random() * symbolCount);
    while (
      (index % size >= 2 && board[index - 1] === next && board[index - 2] === next) ||
      (index >= size * 2 && board[index - size] === next && board[index - size * 2] === next)
    ) {
      next = Math.floor(Math.random() * symbolCount);
    }
    board[index] = next;
  }
  return board;
}

function resolveBoardCopy(board, size) {
  let total = 0;
  while (true) {
    const matched = getMatchSet(board, size);
    if (!matched.size) break;
    total += matched.size;
    matched.forEach((index) => {
      board[index] = null;
    });
    collapseBoard(board, size);
  }
  return total;
}

function evaluateSwapClear(board, size, indexA, indexB) {
  const draft = board.slice();
  [draft[indexA], draft[indexB]] = [draft[indexB], draft[indexA]];
  if (!getMatchSet(draft, size).size) return 0;
  return resolveBoardCopy(draft, size);
}

function hasPlayableMove(board, size) {
  for (let row = 0; row < size; row += 1) {
    for (let col = 0; col < size; col += 1) {
      const index = row * size + col;
      if (col + 1 < size && evaluateSwapClear(board, size, index, index + 1) > 0) return true;
      if (row + 1 < size && evaluateSwapClear(board, size, index, index + size) > 0) return true;
    }
  }
  return false;
}

function createBoard(size, symbolCount) {
  let fallbackBoard = null;
  let bestBoard = null;
  let bestClear = 0;

  for (let attempt = 0; attempt < 48; attempt += 1) {
    const candidate = createBaseBoard(size, symbolCount);
    if (!hasPlayableMove(candidate, size)) continue;
    if (!fallbackBoard) fallbackBoard = candidate.slice();

    let candidateBest = 0;
    for (let row = 0; row < size; row += 1) {
      for (let col = 0; col < size; col += 1) {
        const index = row * size + col;
        if (col + 1 < size) candidateBest = Math.max(candidateBest, evaluateSwapClear(candidate, size, index, index + 1));
        if (row + 1 < size) candidateBest = Math.max(candidateBest, evaluateSwapClear(candidate, size, index, index + size));
      }
    }

    if (candidateBest > bestClear) {
      bestClear = candidateBest;
      bestBoard = candidate.slice();
    }
    if (bestClear >= 6) break;
  }

  return bestBoard || fallbackBoard || createBaseBoard(size, symbolCount);
}

function getMatchSet(board, size) {
  const matched = new Set();
  for (let row = 0; row < size; row += 1) {
    for (let col = 0; col < size - 2; col += 1) {
      const index = row * size + col;
      const value = board[index];
      if (value === null) continue;
      if (board[index + 1] === value && board[index + 2] === value) {
        matched.add(index);
        matched.add(index + 1);
        matched.add(index + 2);
      }
    }
  }
  for (let col = 0; col < size; col += 1) {
    for (let row = 0; row < size - 2; row += 1) {
      const index = row * size + col;
      const value = board[index];
      if (value === null) continue;
      if (board[index + size] === value && board[index + size * 2] === value) {
        matched.add(index);
        matched.add(index + size);
        matched.add(index + size * 2);
      }
    }
  }
  return matched;
}

function collapseBoard(board, size) {
  const tileCount = getMatch3Tiles().length;
  for (let col = 0; col < size; col += 1) {
    const values = [];
    for (let row = size - 1; row >= 0; row -= 1) {
      const index = row * size + col;
      if (board[index] !== null) values.push(board[index]);
    }
    while (values.length < size) {
      values.push(Math.floor(Math.random() * tileCount));
    }
    for (let row = size - 1; row >= 0; row -= 1) {
      board[row * size + col] = values[size - 1 - row];
    }
  }
}

function areAdjacent(indexA, indexB, size) {
  const rowA = Math.floor(indexA / size);
  const rowB = Math.floor(indexB / size);
  const colA = indexA % size;
  const colB = indexB % size;
  return Math.abs(rowA - rowB) + Math.abs(colA - colB) === 1;
}

function getMatch3MotionConfig() {
  return {
    // 消除：0.2s 内先轻微放大，再收缩到 0。
    clearDurationMs: 200,
    clearPeakScale: 1.2,
    // 掉落速度：每多掉 1 格，额外增加一点时间；这两项决定整体手感。
    fallDurationPerCellMs: 92,
    minFallDurationMs: 160,
    maxFallDurationMs: 360,
    // 可切换掉落缓动：expo 更干净，back 更有蓄力感。
    fallEase: "expo",
    // 回弹力度：height 控制幅度，duration 控制抖动时间。
    bounceHeightPx: 10,
    bounceDurationMs: 130,
    clearParticleCount: 8,
  };
}

function waitForAnimationFrame() {
  return new Promise((resolve) => {
    requestAnimationFrame(() => resolve());
  });
}

function animateOverTime(durationMs, onUpdate) {
  return new Promise((resolve) => {
    const start = performance.now();

    function step(now) {
      const elapsed = now - start;
      const progress = durationMs <= 0 ? 1 : Math.min(1, elapsed / durationMs);
      onUpdate(progress);
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        resolve();
      }
    }

    requestAnimationFrame(step);
  });
}

function easeOutExpo(progress) {
  if (progress >= 1) return 1;
  return 1 - 2 ** (-10 * progress);
}

function easeInBack(progress) {
  const s = 1.70158;
  return progress * progress * ((s + 1) * progress - s);
}

function getMatch3FallEase(progress, easeName) {
  return easeName === "back" ? easeInBack(progress) : easeOutExpo(progress);
}

function getMatch3BoardTileNode(index) {
  return el.match3Board.querySelector(`.match3-tile[data-index="${index}"]`);
}

function getMatch3TileDataByValue(value) {
  const tiles = getMatch3Tiles();
  return tiles[((value % tiles.length) + tiles.length) % tiles.length];
}

function spawnMatch3ClearParticles(index, value) {
  const tileNode = getMatch3BoardTileNode(index);
  const boardRect = el.match3Board.getBoundingClientRect();
  const tileRect = tileNode?.getBoundingClientRect();
  if (!tileNode || !tileRect) return;

  const motion = getMatch3MotionConfig();
  const tileData = getMatch3TileDataByValue(value);
  const originX = tileRect.left - boardRect.left + tileRect.width / 2;
  const originY = tileRect.top - boardRect.top + tileRect.height / 2;
  const color = tileData?.particleColor || "rgba(255,255,255,0.92)";

  for (let i = 0; i < motion.clearParticleCount; i += 1) {
    const particle = document.createElement("span");
    particle.className = "match3-clear-particle";
    const angle = (Math.PI * 2 * i) / motion.clearParticleCount + Math.random() * 0.36;
    const distance = 16 + Math.random() * 24;
    const driftX = Math.cos(angle) * distance;
    const driftY = Math.sin(angle) * distance - (10 + Math.random() * 10);
    particle.style.left = `${originX}px`;
    particle.style.top = `${originY}px`;
    particle.style.setProperty("--dx", `${driftX}px`);
    particle.style.setProperty("--dy", `${driftY}px`);
    particle.style.setProperty("--particle-color", color);
    particle.style.animationDelay = `${Math.random() * 40}ms`;
    el.match3Board.appendChild(particle);
    window.setTimeout(() => particle.remove(), 420);
  }
}

async function performMatch3Clear(session, matchedSet) {
  const indices = Array.from(matchedSet);
  if (!indices.length) return;

  const motion = getMatch3MotionConfig();
  const animatedNodes = indices
    .map((index) => ({
      index,
      value: session.board[index],
      node: getMatch3BoardTileNode(index),
    }))
    .filter((entry) => entry.node);

  animatedNodes.forEach((entry) => {
    spawnMatch3ClearParticles(entry.index, entry.value);
    entry.node.style.willChange = "transform, opacity, filter";
  });

  await animateOverTime(motion.clearDurationMs, (progress) => {
    animatedNodes.forEach(({ node }) => {
      if (!node) return;
      let scale = 1;
      if (progress < 0.5) {
        const t = progress / 0.5;
        scale = 1 + (motion.clearPeakScale - 1) * t;
      } else {
        const t = (progress - 0.5) / 0.5;
        scale = motion.clearPeakScale * (1 - t);
      }
      node.style.transform = `scale(${Math.max(0, scale)})`;
      node.style.opacity = `${Math.max(0, 1 - progress * 0.9)}`;
      node.style.filter = `brightness(${1 + progress * 0.16})`;
    });
  });

  animatedNodes.forEach(({ node }) => {
    if (!node) return;
    node.style.transform = "";
    node.style.opacity = "";
    node.style.filter = "";
    node.style.willChange = "";
  });
}

function collapseBoardWithMetadata(board, size) {
  const tileCount = getMatch3Tiles().length;
  const moves = [];

  for (let col = 0; col < size; col += 1) {
    const survivors = [];
    for (let row = size - 1; row >= 0; row -= 1) {
      const index = row * size + col;
      if (board[index] !== null) {
        survivors.push({ value: board[index], sourceRow: row });
      }
    }

    const missing = size - survivors.length;
    for (let i = 0; i < missing; i += 1) {
      survivors.push({
        value: Math.floor(Math.random() * tileCount),
        sourceRow: -1 - i,
      });
    }

    for (let row = size - 1; row >= 0; row -= 1) {
      const targetIndex = row * size + col;
      const item = survivors[size - 1 - row];
      board[targetIndex] = item.value;
      const distance = item.sourceRow - row;
      if (distance !== 0) {
        moves.push({
          targetIndex,
          distance: Math.abs(distance),
        });
      }
    }
  }

  return moves;
}

async function animateMatch3Fall(node, distance, motion) {
  if (!node || distance <= 0) return;

  const tileRect = node.getBoundingClientRect();
  const startOffset = -tileRect.height * distance;
  const mainDuration = Math.max(motion.minFallDurationMs, Math.min(motion.maxFallDurationMs, distance * motion.fallDurationPerCellMs));
  const bounceDuration = motion.bounceDurationMs;
  node.style.willChange = "transform";

  await animateOverTime(mainDuration, (progress) => {
    const eased = getMatch3FallEase(progress, motion.fallEase);
    const currentY = startOffset * (1 - eased);
    node.style.transform = `translateY(${currentY}px)`;
  });

  await animateOverTime(bounceDuration, (progress) => {
    let offset = 0;
    if (progress < 0.34) {
      offset = (motion.bounceHeightPx * 0.35 * progress) / 0.34;
    } else if (progress < 0.68) {
      const t = (progress - 0.34) / 0.34;
      offset = motion.bounceHeightPx * 0.35 + (-motion.bounceHeightPx * 1.15 - motion.bounceHeightPx * 0.35) * t;
    } else {
      const t = (progress - 0.68) / 0.32;
      offset = -motion.bounceHeightPx * 1.15 * (1 - t);
    }
    node.style.transform = `translateY(${offset}px)`;
  });

  node.style.transform = "";
  node.style.willChange = "";
}

async function applyMatch3Gravity(session) {
  const moves = collapseBoardWithMetadata(session.board, session.size);
  renderMatch3Board();
  await waitForAnimationFrame();

  const motion = getMatch3MotionConfig();
  await Promise.all(
    moves.map(({ targetIndex, distance }) => animateMatch3Fall(getMatch3BoardTileNode(targetIndex), distance, motion)),
  );
}

function checkMatch3Matches(session) {
  return getMatchSet(session.board, session.size);
}

async function resolveMatch3Cascade(session, comboDepth = 0) {
  const matched = checkMatch3Matches(session);
  if (!matched.size) {
    return { cleared: 0, combos: comboDepth };
  }

  session.comboCount = comboDepth + 1;
  await waitForAnimationFrame();
  await performMatch3Clear(session, matched);

  matched.forEach((index) => {
    session.board[index] = null;
  });

  const clearedThisRound = matched.size;
  session.cleared += clearedThisRound;
  renderMiniStats(getMatch3StatBadges(session));

  await applyMatch3Gravity(session);

  const next = await resolveMatch3Cascade(session, comboDepth + 1);
  return {
    cleared: clearedThisRound + next.cleared,
    combos: next.combos,
  };
}

function initMatch3() {
  const match3Tiles = getMatch3Tiles();
  const session = {
    type: "match3",
    size: 5,
    moves: 10,
    maxMoves: 10,
    target: 8,
    cleared: 0,
    selected: null,
    board: createBoard(5, match3Tiles.length),
    dropAnimation: true,
    animating: false,
    comboCount: 0,
  };
  stateStore.miniSession = session;
  el.match3Board.classList.remove("hidden");
  renderMiniStats(getMatch3StatBadges(session));
  setMiniFeedback(`首局放宽，直接滑动图块就能交换。利用 ${getMatch3LegendText()} 四种元素压住今夜的风声。`);
  renderMatch3Board();
}

function renderMatch3Board() {
  const session = stateStore.miniSession;
  if (!session || session.type !== "match3") return;
  const tiles = getMatch3Tiles();

  el.match3Board.style.gridTemplateColumns = `repeat(${session.size}, minmax(0, 1fr))`;
  el.match3Board.innerHTML = "";
  session.board.forEach((value, index) => {
    const tile = document.createElement("button");
    tile.className = "match3-tile";
    tile.dataset.index = String(index);
    if (session.selected === index) tile.classList.add("selected");
    if (session.dropAnimation) {
      tile.classList.add("is-dropping");
      tile.style.setProperty("--drop-delay", `${Math.floor(index / session.size) * 28}ms`);
      tile.style.setProperty("--drop-distance", `${18 + Math.floor(index / session.size) * 10}px`);
    }
    applyMatch3TileAppearance(tile, tiles[value]);
    tile.addEventListener("click", () => onMatch3Click(index));
    el.match3Board.appendChild(tile);
  });
  session.dropAnimation = false;
}

async function tryMatch3Swap(fromIndex, toIndex, triggeredBySwipe = false) {
  const session = stateStore.miniSession;
  if (!session || session.type !== "match3" || stateStore.completedMiniGameResult || session.animating) return;

  if (!areAdjacent(fromIndex, toIndex, session.size)) return;

  session.animating = true;
  session.moves -= 1;
  [session.board[fromIndex], session.board[toIndex]] = [session.board[toIndex], session.board[fromIndex]];
  session.selected = null;
  renderMiniStats(getMatch3StatBadges(session));
  renderMatch3Board();

  try {
    const immediateMatches = checkMatch3Matches(session);
    if (!immediateMatches.size) {
      [session.board[fromIndex], session.board[toIndex]] = [session.board[toIndex], session.board[fromIndex]];
      renderMatch3Board();
      setMiniFeedback(triggeredBySwipe ? "这一下没连上，换个方向再试试。" : "这次换位没有制造连消，换个手位再试。");
      return;
    }

    const result = await resolveMatch3Cascade(session, 0);
    let bonusText = "";
    if (result.combos >= 2 && session.moves < session.maxMoves) {
      session.moves += 1;
      bonusText = " 连坠奖励 +1 步。";
    }
    setMiniFeedback(
      `一下清掉 ${result.cleared} 枚。${result.combos >= 2 ? `连锁来到 ${result.combos} Combo，` : ""}场面顺了许多。${bonusText}`,
    );
    renderMiniStats(getMatch3StatBadges(session));
    renderMatch3Board();

    if (session.cleared >= session.target) {
      finishMiniGame(true, session.cleared, "你顺手连出几波下落，把前厅里的怀疑声压了下去。");
    } else if (session.moves <= 0) {
      finishMiniGame(false, session.cleared, "你只压下了一半风声，还是有人盯上了你。");
    }
  } finally {
    session.comboCount = 0;
    session.animating = false;
  }
}

function onMatch3Click(index) {
  const session = stateStore.miniSession;
  if (!session || session.type !== "match3" || stateStore.completedMiniGameResult || session.animating) return;
  if (Date.now() < stateStore.suppressMatch3ClickUntil) return;

  if (session.selected === null) {
    session.selected = index;
    renderMatch3Board();
    return;
  }

  if (session.selected === index) {
    session.selected = null;
    renderMatch3Board();
    return;
  }

  if (!areAdjacent(session.selected, index, session.size)) {
    session.selected = index;
    renderMatch3Board();
    setMiniFeedback("先点住一枚，再换到挨着的格子；也可以直接滑一下。");
    return;
  }

  void tryMatch3Swap(session.selected, index);
}

function getSwipeTargetIndex(startIndex, direction, size) {
  const row = Math.floor(startIndex / size);
  const col = startIndex % size;
  if (direction === "left" && col > 0) return startIndex - 1;
  if (direction === "right" && col < size - 1) return startIndex + 1;
  if (direction === "up" && row > 0) return startIndex - size;
  if (direction === "down" && row < size - 1) return startIndex + size;
  return null;
}

function onMatch3PointerDown(event) {
  const session = stateStore.miniSession;
  if (!session || session.type !== "match3" || stateStore.completedMiniGameResult || session.animating) return;
  const tile = event.target.closest(".match3-tile");
  if (!tile) return;

  stateStore.match3Swipe = {
    startIndex: Number(tile.dataset.index),
    startX: event.clientX,
    startY: event.clientY,
  };
}

function onMatch3PointerUp(event) {
  const session = stateStore.miniSession;
  const swipe = stateStore.match3Swipe;
  stateStore.match3Swipe = null;
  if (!swipe || !session || session.type !== "match3" || stateStore.completedMiniGameResult || session.animating) return;

  const dx = event.clientX - swipe.startX;
  const dy = event.clientY - swipe.startY;
  const distance = Math.max(Math.abs(dx), Math.abs(dy));
  if (distance < 18) return;

  const direction = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? "right" : "left") : dy > 0 ? "down" : "up";
  const targetIndex = getSwipeTargetIndex(swipe.startIndex, direction, session.size);
  if (targetIndex === null) return;

  stateStore.suppressMatch3ClickUntil = Date.now() + 220;
  void tryMatch3Swap(swipe.startIndex, targetIndex, true);
}

function randomEmptyIndex(board) {
  const empty = [];
  board.forEach((value, index) => {
    if (value === 0) empty.push(index);
  });
  if (!empty.length) return -1;
  return empty[Math.floor(Math.random() * empty.length)];
}

function getMergeStatBadges(session) {
  return [
    "启用素材 01/02/03",
    `目标合成 03 ${MERGE_TILES[3].label}`,
    `剩余步数 ${session.moves}`,
    `当前最高 ${String(session.maxLevel).padStart(2, "0")}`,
  ];
}

function initMerge() {
  const board = Array(16).fill(0);
  [1, 1, 1, 1, 2].forEach((value) => {
    const index = randomEmptyIndex(board);
    board[index] = value;
  });
  stateStore.miniSession = {
    type: "merge",
    board,
    selected: null,
    moves: 6,
    mergeCount: 0,
    maxLevel: 2,
    triggeredEvent: "",
  };
  el.mergeBoard.classList.remove("hidden");
  renderMiniStats(getMergeStatBadges(stateStore.miniSession));
  setMiniFeedback("把相同素材两两整编升阶，先拼出 03“封蜡信笺”。");
  renderMergeBoard();
}

function renderMergeBoard() {
  const session = stateStore.miniSession;
  if (!session || session.type !== "merge") return;

  el.mergeBoard.innerHTML = "";
  session.board.forEach((value, index) => {
    const tile = document.createElement("button");
    tile.className = "merge-tile";
    tile.dataset.index = String(index);
    tile.dataset.level = String(value);
    if (value === 0) tile.classList.add("empty");
    if (session.selected === index) tile.classList.add("selected");
    const tileData = MERGE_TILES[value] || MERGE_TILES[3];
    tile.style.background = tileData.color;
    tile.setAttribute("aria-label", tileData.label || "空位");
    tile.innerHTML = "";
    if (value !== 0) {
      const badge = document.createElement("span");
      badge.className = "merge-code";
      badge.textContent = tileData.code;

      const icon = document.createElement("img");
      icon.className = "merge-icon";
      icon.src = tileData.imageUrl;
      icon.alt = tileData.label;

      const label = document.createElement("span");
      label.className = "merge-label";
      label.textContent = tileData.label;

      tile.append(icon, badge, label);
    }
    tile.addEventListener("click", () => onMergeClick(index));
    el.mergeBoard.appendChild(tile);
  });
}

function onMergeClick(index) {
  const session = stateStore.miniSession;
  if (!session || session.type !== "merge" || stateStore.completedMiniGameResult) return;
  if (session.board[index] === 0) return;

  if (session.selected === null) {
    session.selected = index;
    renderMergeBoard();
    return;
  }

  if (session.selected === index) {
    session.selected = null;
    renderMergeBoard();
    return;
  }

  const source = session.selected;
  const sourceValue = session.board[source];
  const targetValue = session.board[index];

  if (sourceValue !== targetValue) {
    session.selected = index;
    renderMergeBoard();
    setMiniFeedback("只能合并同等级情报。");
    return;
  }

  session.board[index] = Math.min(targetValue + 1, 3);
  session.board[source] = 0;
  session.selected = null;
  session.moves -= 1;
  session.mergeCount += 1;
  session.maxLevel = Math.max(session.maxLevel, session.board[index]);
  const spawnIndex = randomEmptyIndex(session.board);
  if (spawnIndex >= 0) session.board[spawnIndex] = Math.random() > 0.8 ? 2 : 1;

  renderMiniStats(getMergeStatBadges(session));
  renderMergeBoard();
  setMiniFeedback(`你把两份线索整编成了 ${String(session.board[index]).padStart(2, "0")}“${MERGE_TILES[session.board[index]].label}”。`);

  if (session.maxLevel >= 3) {
    session.triggeredEvent = "sects_joined";
    setMiniNotice("异讯成卷：本届武林大会，拜月教与五毒教将首次同场参会。", "event");
    finishMiniGame(
      true,
      session.maxLevel * 10 + session.mergeCount,
      "你拼出了 03“封蜡信笺”，从中确认了拜月教与五毒教首次参加武林大会的消息。",
      { achieved_level: session.maxLevel, triggered_event: session.triggeredEvent },
    );
  } else if (session.moves <= 0) {
    finishMiniGame(
      false,
      session.maxLevel * 6 + session.mergeCount,
      "你没能在开场前拼出 03“封蜡信笺”，只能带着半截消息进前厅。",
      { achieved_level: session.maxLevel },
    );
  }
}

function randomFood(snake, size) {
  while (true) {
    const next = { x: Math.floor(Math.random() * size), y: Math.floor(Math.random() * size) };
    if (!snake.some((segment) => segment.x === next.x && segment.y === next.y)) return next;
  }
}

function drawSnake() {
  const session = stateStore.miniSession;
  if (!session || session.type !== "snake") return;

  const ctx = el.snakeCanvas.getContext("2d");
  const cell = el.snakeCanvas.width / session.size;
  ctx.clearRect(0, 0, el.snakeCanvas.width, el.snakeCanvas.height);
  ctx.fillStyle = "#f4eadc";
  ctx.fillRect(0, 0, el.snakeCanvas.width, el.snakeCanvas.height);

  ctx.strokeStyle = "rgba(111, 67, 38, 0.08)";
  for (let i = 0; i < session.size; i += 1) {
    ctx.beginPath();
    ctx.moveTo(i * cell, 0);
    ctx.lineTo(i * cell, el.snakeCanvas.height);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(0, i * cell);
    ctx.lineTo(el.snakeCanvas.width, i * cell);
    ctx.stroke();
  }

  ctx.fillStyle = "#9f6f3f";
  session.snake.forEach((segment, index) => {
    const inset = index === 0 ? 3 : 5;
    ctx.fillRect(segment.x * cell + inset, segment.y * cell + inset, cell - inset * 2, cell - inset * 2);
  });

  ctx.fillStyle = "#a45f51";
  ctx.beginPath();
  ctx.arc(session.food.x * cell + cell / 2, session.food.y * cell + cell / 2, cell / 3, 0, Math.PI * 2);
  ctx.fill();
}

function setSnakeDirection(direction) {
  const session = stateStore.miniSession;
  if (!session || session.type !== "snake") return;
  const opposites = { up: "down", down: "up", left: "right", right: "left" };
  if (opposites[direction] === session.direction) return;
  session.pendingDirection = direction;
}

function moveSnake() {
  const session = stateStore.miniSession;
  if (!session || session.type !== "snake" || stateStore.completedMiniGameResult) return;

  session.direction = session.pendingDirection || session.direction;
  const vector = {
    up: { x: 0, y: -1 },
    down: { x: 0, y: 1 },
    left: { x: -1, y: 0 },
    right: { x: 1, y: 0 },
  }[session.direction];
  const head = { x: session.snake[0].x + vector.x, y: session.snake[0].y + vector.y };

  if (
    head.x < 0 ||
    head.y < 0 ||
    head.x >= session.size ||
    head.y >= session.size ||
    session.snake.some((segment) => segment.x === head.x && segment.y === head.y)
  ) {
    finishMiniGame(false, session.score, "你在街巷追索时撞进死角，情报链断了。");
    return;
  }

  session.snake.unshift(head);
  if (head.x === session.food.x && head.y === session.food.y) {
    session.score += 1;
    session.food = randomFood(session.snake, session.size);
    setMiniFeedback(`你追上了一条风声，目前已收拢 ${session.score} 条。`);
  } else {
    session.snake.pop();
  }

  renderMiniStats([`目标风声 ${session.goal}`, `已收拢 ${session.score}`, `剩余时间 ${session.timeLeft}s`]);
  drawSnake();

  if (session.score >= session.goal) {
    finishMiniGame(true, session.score * 4, "你在时限内收拢了足够多的风声，情报网开始成形。");
  }
}

function initSnake() {
  stateStore.miniSession = {
    type: "snake",
    size: 10,
    snake: [
      { x: 2, y: 5 },
      { x: 1, y: 5 },
      { x: 0, y: 5 },
    ],
    direction: "right",
    pendingDirection: "right",
    food: { x: 4, y: 5 },
    goal: 2,
    score: 0,
    timeLeft: 24,
  };

  el.snakeWrap.classList.remove("hidden");
  renderMiniStats(["目标风声 2", "已收拢 0", "剩余时间 24s"]);
  setMiniFeedback("这一局放宽了，先追到 2 条风声就能过关。");
  drawSnake();

  stateStore.snakeLoop = setInterval(moveSnake, 240);
  stateStore.snakeTimer = setInterval(() => {
    const session = stateStore.miniSession;
    if (!session || session.type !== "snake" || stateStore.completedMiniGameResult) return;
    session.timeLeft -= 1;
    renderMiniStats([`目标风声 ${session.goal}`, `已收拢 ${session.score}`, `剩余时间 ${session.timeLeft}s`]);
    if (session.timeLeft <= 0) {
      if (session.score >= session.goal) {
        finishMiniGame(true, session.score * 4, "你踩着时限把最后几条风声也收进了囊中。");
      } else {
        finishMiniGame(false, session.score * 3, "时限到了，你只追回了部分风声。");
      }
    }
  }, 1000);
}

async function startMiniGame() {
  if (!stateStore.pendingMiniGame) return;
  resetMiniStage();
  if (stateStore.pendingMiniGame.type === "match3") {
    await loadMatch3Atlas();
    initMatch3();
  }
  if (stateStore.pendingMiniGame.type === "merge") initMerge();
  if (stateStore.pendingMiniGame.type === "snake") initSnake();
}

el.openingStartButton?.addEventListener("click", () => startChapter({ autoStartOpeningMerge: true }));
el.startButton.addEventListener("click", () => startChapter({ autoStartOpeningMerge: true }));
el.restartButton.addEventListener("click", () => startChapter({ autoStartOpeningMerge: true }));
el.freeSubmit.addEventListener("click", () => {
  const defaultChoice = stateStore.currentScene?.choices?.[0] || {
    id: "free-steady",
    label: "自由发话",
    intent: "steady",
    risk_hint: "使用默认稳场意图",
  };
  advanceScene(defaultChoice);
});
el.closeMiniButton.addEventListener("click", closeMiniOverlay);
el.miniStartButton.addEventListener("click", startMiniGame);
el.miniSubmitButton.addEventListener("click", submitMiniGameResult);
el.match3Board.addEventListener("pointerdown", onMatch3PointerDown);
el.dirButtons.forEach((button) => {
  button.addEventListener("click", () => setSnakeDirection(button.dataset.dir));
});

window.addEventListener("pointerup", onMatch3PointerUp);
window.addEventListener("pointercancel", () => {
  stateStore.match3Swipe = null;
});

window.addEventListener("keydown", (event) => {
  const mapping = {
    ArrowUp: "up",
    ArrowDown: "down",
    ArrowLeft: "left",
    ArrowRight: "right",
  };
  if (mapping[event.key]) {
    event.preventDefault();
    setSnakeDirection(mapping[event.key]);
  }
});

renderRapport({
  莫红绫: 78,
  南宫翊: 28,
  谢扶摇: 18,
  江潋: 36,
  晏无秋: 14,
});

el.hubChat?.addEventListener("click", () => openHubOverlay("chat"));
el.hubItems?.addEventListener("click", () => openHubOverlay("items"));
el.hubFactions?.addEventListener("click", () => openHubOverlay("factions"));
el.hubCustom?.addEventListener("click", () => openHubOverlay("custom"));

el.wechatClose?.addEventListener("click", () => {
  closeHubOverlays();
});

el.wechatBack?.addEventListener("click", () => {
  showWechatHome();
});

el.wechatSend?.addEventListener("click", sendWechatMessage);
el.wechatInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    sendWechatMessage();
  }
});
el.wechatGift?.addEventListener("click", () => openGiftPicker());
el.giftPickerClose?.addEventListener("click", () => closeGiftPicker());
el.giftPicker?.addEventListener("click", (ev) => {
  if (ev.target === el.giftPicker) closeGiftPicker();
});

document.querySelectorAll(".hub-sheet-close").forEach((btn) => {
  btn.addEventListener("click", () => closeHubOverlays());
});

el.intelDetailClose?.addEventListener("click", (e) => {
  e.stopPropagation();
  closeIntelDetailModal();
});
el.intelDetailSell?.addEventListener("click", () => {
  const sid = el.intelDetailOverlay?.dataset.activeSecret;
  if (sid) void sellIntelFromDetail(sid);
});
el.intelDetailOverlay?.addEventListener("click", (ev) => {
  if (ev.target === el.intelDetailOverlay) closeIntelDetailModal();
});
el.intelDetailOverlay?.querySelector(".intel-detail-sheet")?.addEventListener("click", (e) => {
  e.stopPropagation();
});

el.customSavePlayer?.addEventListener("click", () => {
  const name = el.customPlayerName.value.trim();
  if (!name) {
    alert("请填写玩家姓名。");
    return;
  }
  stateStore.playerName = name;
  saveProfile();
  alert("姓名已保存，新开章或下一回合请求将使用此名。");
});

el.customAddNpc?.addEventListener("click", () => {
  const name = el.customNpcName.value.trim();
  const personality = el.customNpcPersonality.value.trim();
  const backstory = el.customNpcBackstory.value.trim();
  if (!name) {
    alert("请填写新 NPC 姓名。");
    return;
  }
  if (!personality || !backstory) {
    alert("请补全性格与来历，方便后续剧情与私聊口吻。");
    return;
  }
  const id = `custom-${Date.now()}`;
  stateStore.customNpcs.push({ id, name, personality, backstory });
  saveCustomNpcs();
  stateStore.chatByContact[id] = [];
  saveChatStore();
  el.customNpcName.value = "";
  el.customNpcPersonality.value = "";
  el.customNpcBackstory.value = "";
  if (stateStore.gameState?.rapport) {
    renderRapport(stateStore.gameState.rapport);
  } else {
    renderRapport({
      莫红绫: 78,
      南宫翊: 28,
      谢扶摇: 18,
      江潋: 36,
      晏无秋: 14,
    });
  }
  renderWechatContacts();
  alert(`「${name}」已加入江湖名录与传书列表。`);
});

syncActionPanel();
void loadMatch3Atlas();
