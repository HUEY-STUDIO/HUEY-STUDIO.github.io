/* 이 페이지 안에서 Supabase 클라이언트는 딱 하나만 만들어 여러 기능(미니 스페이스·
   로그인 패널·관리자 패널)이 나눠 쓴다. 같은 프로젝트로 클라이언트를 여러 개 만들면
   전부 같은 localStorage 키(세션 저장소)를 두고 서로 경합해 "어떤 부분은 로그인을
   알아채고 어떤 부분은 못 알아채는" 것 같은 불일치가 생길 수 있다 — 실제로 겪었던
   문제라 반드시 이렇게 한 번만 만든다. */
function heuySupabase() {
  if (!window.supabase || !window.supabase.createClient) return null;
  if (!window.__heuySb) {
    window.__heuySb = window.supabase.createClient(
      "https://rwmivexpkjppvsvwuguw.supabase.co",
      "sb_publishable_iDTkwOY5Qo42G0xj7Igqaw_rgfrWMyH"
    );
  }
  return window.__heuySb;
}

/* 홈페이지 본문/사이드바 경계 드래그 리사이즈. Supabase 여부와 무관하게 항상 동작하고,
   고른 사이드바 폭은 localStorage에 저장해 다음 방문에도 유지한다. */
(function () {
  "use strict";
  var resizer = document.getElementById("homeResizer");
  var layout = document.getElementById("homeLayout");
  if (!resizer || !layout) return;

  var LS_KEY = "heuy_sidebar_w";
  var MIN = 220, MAX = 480;

  function apply(px) {
    layout.style.gridTemplateColumns = "1fr 10px " + px + "px";
  }
  function sideWidth() {
    return document.querySelector(".home-side").getBoundingClientRect().width;
  }
  function clamp(px) { return Math.min(MAX, Math.max(MIN, px)); }

  try {
    var saved = parseInt(localStorage.getItem(LS_KEY), 10);
    if (saved) apply(clamp(saved));
  } catch (e) {}

  var dragging = false, startX = 0, startWidth = 0;

  function start(clientX) {
    dragging = true;
    startX = clientX;
    startWidth = sideWidth();
    resizer.classList.add("is-dragging");
    document.body.style.userSelect = "none";
  }
  function move(clientX) {
    if (!dragging) return;
    apply(clamp(startWidth - (clientX - startX)));
  }
  function end() {
    if (!dragging) return;
    dragging = false;
    resizer.classList.remove("is-dragging");
    document.body.style.userSelect = "";
    try { localStorage.setItem(LS_KEY, Math.round(sideWidth())); } catch (e) {}
  }

  resizer.addEventListener("mousedown", function (e) { start(e.clientX); e.preventDefault(); });
  window.addEventListener("mousemove", function (e) { move(e.clientX); });
  window.addEventListener("mouseup", end);

  resizer.addEventListener("touchstart", function (e) { start(e.touches[0].clientX); }, { passive: true });
  window.addEventListener("touchmove", function (e) { move(e.touches[0].clientX); }, { passive: true });
  window.addEventListener("touchend", end);

  // 키보드로도 조절 가능하게(접근성)
  resizer.addEventListener("keydown", function (e) {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    var next = clamp(sideWidth() + (e.key === "ArrowLeft" ? 16 : -16));
    apply(next);
    try { localStorage.setItem(LS_KEY, Math.round(next)); } catch (err) {}
  });
})();

/* 미니 스페이스 — 계정 패널 아래 붙는 공유 스페이스. 방향키로 픽셀 캐릭터를 자유롭게
   (대각선 포함) 부드럽게 움직인다. 열린 월드라 방 하나에 다 안 들어가는 만큼, 카메라가
   내 캐릭터를 화면 중앙에 고정한 채 .ms-platform 전체를 매 프레임 이동시킨다 —
   실제 위치는 저장하지 않는다(그냥 놀이용).

   진짜 3D 회전(rotateX/rotateZ) 대신 고전적인 2:1 아이소메트릭 투영을 쓴다 — 좌표를
   화면 다이아몬드로 매핑만 하는 방식이라 박스섀도 픽셀아트가 회전으로 흐려지지 않고
   또렷하게 남는다. WORLD_* / ISO_* 상수는 render.py의 MS_* 와 반드시 맞물려야 한다.

   접속자끼리는 Supabase Realtime의 presence(누가 있는지)+broadcast(움직임)로
   동기화한다 — 위치를 DB에 쓰지 않는 휘발성 채널이라 움직일 때마다 테이블에
   기록하는 부담이 없다. */
(function () {
  "use strict";
  var room = document.getElementById("msRoom");
  var platform = document.getElementById("msPlatform");
  var char = document.getElementById("msChar");
  var playersWrap = document.getElementById("msPlayers");
  var onlineBadge = document.getElementById("msOnline");
  var myTag = document.getElementById("msMyTag");
  var chatForm = document.getElementById("msChatForm");
  var chatInput = document.getElementById("msChatInput");
  if (!room || !platform || !char) return;
  char.classList.add("ms-char--me");

  var WORLD_MAX = 50;              // gx, gy 범위 [0, WORLD_MAX] — render.py MS_WORLD_MAX
  var ISO_ORIGIN_X = 550, ISO_ORIGIN_Y = 0;
  var ISO_TW = 11, ISO_TH = 5.5;
  var CHAR_W = 20, FOOT_OFFSET = 24; // 캐릭터 "발"이 투영점에 오도록

  var gx = WORLD_MAX / 2, gy = WORLD_MAX / 2;

  function project(px, py) {
    return {
      x: ISO_ORIGIN_X + (px - py) * ISO_TW,
      y: ISO_ORIGIN_Y + (px + py) * ISO_TH
    };
  }
  function darken(hex) {
    var m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
    if (!m) return hex;
    var n = parseInt(m[1], 16);
    var r = Math.max(0, ((n >> 16) & 255) - 40);
    var g = Math.max(0, ((n >> 8) & 255) - 40);
    var b = Math.max(0, (n & 255) - 40);
    return "#" + [r, g, b].map(function (v) { return ("0" + v.toString(16)).slice(-2); }).join("");
  }
  function myColorHex() {
    return getComputedStyle(char).getPropertyValue("--char-a").trim() || "#FF4D1A";
  }

  // 카메라: 내 캐릭터가 뷰포트 중앙에 오도록 .ms-platform 전체를 밀어낸다.
  function paint() {
    var p = project(gx, gy);
    var vw = room.clientWidth, vh = room.clientHeight;
    platform.style.transform = "translate(" + (vw / 2 - p.x) + "px," + (vh / 2 - p.y) + "px)";
    char.style.left = (p.x - CHAR_W / 2) + "px";
    char.style.top = (p.y - FOOT_OFFSET) + "px";
  }
  paint();

  // ---------------------------------------------------------- 다른 접속자 동기화
  var others = Object.create(null); // id -> {el, gx, gy}
  var channel = null;
  var myId = "g_" + Math.random().toString(36).slice(2, 10);
  var myName = "손님" + Math.floor(1000 + Math.random() * 9000);

  function positionOther(rec) {
    var p = project(rec.gx, rec.gy);
    rec.el.style.left = (p.x - CHAR_W / 2) + "px";
    rec.el.style.top = (p.y - FOOT_OFFSET) + "px";
  }
  function ensureOther(id, name, color) {
    var rec = others[id];
    if (rec) return rec;
    var el = document.createElement("div");
    el.className = "ms-char ms-char--other";
    el.style.setProperty("--char-a", color || "#7A716B");
    el.style.setProperty("--char-a-dk", darken(color || "#7A716B"));
    el.innerHTML = '<div class="ms-char-body"></div><div class="ms-char-tag"></div>';
    playersWrap.appendChild(el);
    rec = others[id] = { el: el, gx: WORLD_MAX / 2, gy: WORLD_MAX / 2 };
    positionOther(rec);
    return rec;
  }
  function setOtherMeta(rec, name, color) {
    rec.el.querySelector(".ms-char-tag").textContent = name || "손님";
    if (color) {
      rec.el.style.setProperty("--char-a", color);
      rec.el.style.setProperty("--char-a-dk", darken(color));
    }
  }
  function removeOther(id) {
    var rec = others[id];
    if (!rec) return;
    rec.el.remove();
    delete others[id];
  }
  function updateOnlineBadge() {
    if (!onlineBadge) return;
    var n = Object.keys(others).length + 1;
    onlineBadge.textContent = "● " + n;
    onlineBadge.classList.toggle("is-live", n > 1);
  }

  // ---------------------------------------------------------- 점프(스페이스바)
  function triggerJump(el) {
    if (!el || el.classList.contains("is-jumping")) return;
    el.classList.add("is-jumping");
    setTimeout(function () { el.classList.remove("is-jumping"); }, 500);
  }
  function broadcastJump() {
    if (!channel) return;
    channel.send({ type: "broadcast", event: "jump", payload: { id: myId } });
  }

  // ---------------------------------------------------------- 채팅(엔터, 말풍선)
  function showBubble(el, text) {
    if (!el) return;
    var old = el.querySelector(".ms-char-bubble");
    if (old) old.remove();
    var b = document.createElement("div");
    b.className = "ms-char-bubble";
    b.textContent = text; // textContent라 별도 이스케이프 없이도 안전
    el.appendChild(b);
    setTimeout(function () { if (b.parentNode) b.remove(); }, 4000);
  }
  function broadcastChat(text) {
    if (!channel) return;
    channel.send({ type: "broadcast", event: "chat", payload: { id: myId, name: myName, color: myColorHex(), text: text } });
  }
  function openChat() {
    if (!chatForm || !chatInput) return;
    chatForm.classList.remove("hidden");
    chatInput.value = "";
    chatInput.focus();
  }
  function closeChat() {
    if (!chatForm) return;
    chatForm.classList.add("hidden");
    room.focus();
  }
  if (chatForm && chatInput) {
    chatForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var text = chatInput.value.trim().slice(0, 60);
      closeChat();
      if (!text) return;
      showBubble(char, text);
      broadcastChat(text);
    });
    chatInput.addEventListener("keydown", function (e) {
      e.stopPropagation(); // 타이핑 중엔 방향키/스페이스가 이동·점프로 새지 않게
      if (e.key === "Escape") { e.preventDefault(); closeChat(); }
    });
  }

  var sb = heuySupabase();
  if (sb) {
    channel = sb.channel("mini_space_v1", { config: { broadcast: { self: false }, presence: { key: myId } } });

    channel.on("broadcast", { event: "move" }, function (msg) {
      var d = msg.payload;
      if (!d || d.id === myId) return;
      var rec = ensureOther(d.id, d.name, d.color);
      setOtherMeta(rec, d.name, d.color);
      rec.gx = d.gx; rec.gy = d.gy;
      positionOther(rec);
    });
    channel.on("broadcast", { event: "jump" }, function (msg) {
      var d = msg.payload;
      if (!d || d.id === myId) return;
      var rec = others[d.id];
      if (rec) triggerJump(rec.el);
    });
    channel.on("broadcast", { event: "chat" }, function (msg) {
      var d = msg.payload;
      if (!d || d.id === myId || !d.text) return;
      var rec = ensureOther(d.id, d.name, d.color);
      setOtherMeta(rec, d.name, d.color);
      showBubble(rec.el, String(d.text).slice(0, 60));
    });
    channel.on("presence", { event: "sync" }, function () {
      var state = channel.presenceState();
      var seen = Object.create(null);
      Object.keys(state).forEach(function (key) {
        (state[key] || []).forEach(function (meta) {
          if (meta.id === myId) return;
          seen[meta.id] = true;
          var rec = ensureOther(meta.id, meta.name, meta.color);
          setOtherMeta(rec, meta.name, meta.color);
          if (typeof meta.gx === "number") { rec.gx = meta.gx; rec.gy = meta.gy; positionOther(rec); }
        });
      });
      Object.keys(others).forEach(function (id) { if (!seen[id]) removeOther(id); });
      updateOnlineBadge();
    });
    channel.subscribe(function (status) {
      if (status === "SUBSCRIBED") {
        channel.track({ id: myId, name: myName, color: myColorHex(), gx: gx, gy: gy });
      }
    });

    // 로그인돼 있으면 실제 닉네임으로 갱신
    sb.auth.getSession().then(function (res) {
      var session = res.data && res.data.session;
      if (!session || !session.user) return;
      myId = session.user.id;
      return sb.from("profiles").select("nickname").eq("id", session.user.id).maybeSingle().then(function (r) {
        var nick = r.data && r.data.nickname;
        myName = nick || (session.user.email || "").split("@")[0] || myName;
        if (myTag) myTag.textContent = myName;
        if (channel) channel.track({ id: myId, name: myName, color: myColorHex(), gx: gx, gy: gy });
      });
    }).catch(function () {});
  }
  if (myTag) myTag.textContent = myName;

  // ---------------------------------------------------------- 이동
  // 화면에서 위/아래/좌/우로 보이도록, 각 방향키를 월드 대각선 한 쌍에 대응시킨다
  // (아이소메트릭 게임의 표준 방식) — 여러 키를 같이 누르면 자연히 나머지 4방향도 나온다.
  var keys = Object.create(null);
  var DIRS = {
    ArrowUp: [-1, -1], ArrowDown: [1, 1],
    ArrowLeft: [-1, 1], ArrowRight: [1, -1]
  };
  var SPEED = 9; // 초당 월드유닛 — 넓어진 만큼 예전보다 빠르게
  var rafId = null, lastT = null, lastSend = 0;

  function clampWorld(v) { return Math.max(0, Math.min(WORLD_MAX, v)); }

  function broadcastMove(t) {
    if (!channel || t - lastSend < 90) return;
    lastSend = t;
    channel.send({ type: "broadcast", event: "move", payload: { id: myId, name: myName, color: myColorHex(), gx: gx, gy: gy } });
  }

  function tick(t) {
    if (lastT == null) lastT = t;
    var dt = Math.min(48, t - lastT);
    lastT = t;
    var dx = 0, dy = 0;
    for (var k in DIRS) {
      if (keys[k]) { dx += DIRS[k][0]; dy += DIRS[k][1]; }
    }
    var len = Math.hypot(dx, dy);
    if (len > 0) {
      var v = SPEED * (dt / 1000);
      gx = clampWorld(gx + (dx / len) * v);
      gy = clampWorld(gy + (dy / len) * v);
      paint();
      broadcastMove(t);
      rafId = requestAnimationFrame(tick);
    } else {
      rafId = null; lastT = null;
    }
  }
  function ensureLoop() {
    if (rafId == null) rafId = requestAnimationFrame(tick);
  }

  room.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      openChat();
      return;
    }
    if (e.code === "Space" || e.key === " ") {
      e.preventDefault();
      triggerJump(char);
      broadcastJump();
      return;
    }
    if (!DIRS[e.key]) return;
    e.preventDefault();
    keys[e.key] = true;
    ensureLoop();
  });
  room.addEventListener("keyup", function (e) {
    if (!DIRS[e.key]) return;
    delete keys[e.key];
  });
  room.addEventListener("blur", function () { keys = Object.create(null); });
  room.addEventListener("click", function () { room.focus(); });
  window.addEventListener("resize", paint);

  // ---- 캐릭터 색 고르기 ----
  var colorsWrap = document.getElementById("msColors");
  if (colorsWrap) {
    var btns = Array.prototype.slice.call(colorsWrap.querySelectorAll(".ms-color-btn"));
    var LS_KEY = "heuy_char_color";

    function applyColor(idx, persist) {
      var btn = btns[idx];
      if (!btn) return;
      var a = getComputedStyle(btn).getPropertyValue("--sw-a").trim();
      char.style.setProperty("--char-a", a);
      char.style.setProperty("--char-a-dk", darken(a));
      btns.forEach(function (b, i) { b.classList.toggle("is-on", i === idx); });
      if (persist) {
        try { localStorage.setItem(LS_KEY, idx); } catch (e) {}
        if (channel) channel.track({ id: myId, name: myName, color: a, gx: gx, gy: gy });
      }
    }
    btns.forEach(function (btn, i) {
      btn.addEventListener("click", function () { applyColor(i, true); });
    });
    var saved = 0;
    try { saved = parseInt(localStorage.getItem(LS_KEY), 10) || 0; } catch (e) {}
    applyColor(saved, false);
  }
})();

/* HEUY.ARCHI — 로그인(매직링크) + 닉네임 + 홈페이지 피드백/댓글 채팅방
   Supabase Auth + Postgres + Realtime. 계정 패널·피드백방 모두 홈페이지 전용이라
   #accountPanel 이 없는 페이지(지난호·카테고리 등)에서는 이 스크립트가 아무 일도 안 한다. */
(function () {
  "use strict";
  var panel = document.getElementById("accountPanel");
  if (!panel) return;
  var sb = heuySupabase();
  if (!sb) {
    // 광고 차단기·네트워크 문제로 supabase-js CDN이 안 불러와지면 버튼을 눌러도
    // 아무 반응이 없어 보이므로, 최소한 이유는 알 수 있게 표시해둔다.
    var note = document.getElementById("authNote");
    if (note) note.textContent = "로그인 모듈을 불러오지 못했습니다. 새로고침해보거나 광고 차단기를 꺼보세요.";
    return;
  }
  console.log("HEUY-DEBUG: account panel init start, sb ready");
  try {

  // ---------------------------------------------------------- 오늘 방문자수
  // 새로고침·재접속마다 page_views에 1행씩 쌓고, 그 날짜(KST) 범위의 누적 건수를
  // 세어 상단바 navVisits에 표시한다. 중복 제거 없이 접속(페이지 로드) 자체를 센다.
  (function () {
    var el = document.getElementById("navVisits");
    if (!el) return;
    var todayKST = new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit"
    }).format(new Date());
    var startISO = todayKST + "T00:00:00+09:00";
    var endISO = new Date(new Date(startISO).getTime() + 86400000).toISOString();

    sb.from("page_views").insert({}).catch(function () {}).then(function () {
      return sb.from("page_views").select("*", { count: "exact", head: true })
        .gte("visited_at", startISO).lt("visited_at", endISO);
    }).then(function (res) {
      if (res && typeof res.count === "number") el.textContent = "오늘 방문 " + res.count.toLocaleString() + "회";
      else el.textContent = "";
    }).catch(function () { el.textContent = ""; });
  })();

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function emailName(user) {
    return ((user && user.email) || "익명").split("@")[0];
  }
  function fmtTime(iso) {
    var d = new Date(iso);
    var now = new Date();
    var sameDay = d.toDateString() === now.toDateString();
    var hh = ("0" + d.getHours()).slice(-2), mm = ("0" + d.getMinutes()).slice(-2);
    if (sameDay) return hh + ":" + mm;
    return (d.getMonth() + 1) + "." + d.getDate() + " " + hh + ":" + mm;
  }

  // ---------------------------------------------------------- 계정 패널
  var apLoggedOut = document.getElementById("apLoggedOut");
  var apLoggedIn = document.getElementById("apLoggedIn");
  var apAvatar = document.getElementById("apAvatar");
  var apAvatarImg = document.getElementById("apAvatarImg");
  var apAvatarLetter = document.getElementById("apAvatarLetter");
  var apAvatarFile = document.getElementById("apAvatarFile");
  var apAvatarNote = document.getElementById("apAvatarNote");
  var apName = document.getElementById("apName");
  var apEmail = document.getElementById("apEmail");
  var apEditNick = document.getElementById("apEditNick");
  var nickForm = document.getElementById("nickForm");
  var nickInput = document.getElementById("nickInput");
  var nickCancel = document.getElementById("nickCancel");
  var authLogout = document.getElementById("authLogout");
  var apTabLogin = document.getElementById("apTabLogin");
  var apTabSignup = document.getElementById("apTabSignup");
  var loginForm = document.getElementById("loginForm");
  var loginEmail = document.getElementById("loginEmail");
  var loginPassword = document.getElementById("loginPassword");
  var signupForm = document.getElementById("signupForm");
  var signupEmail = document.getElementById("signupEmail");
  var signupPassword = document.getElementById("signupPassword");
  var signupNick = document.getElementById("signupNick");
  var authNote = document.getElementById("authNote");
  var apForgotPw = document.getElementById("apForgotPw");
  var apResetPassword = document.getElementById("apResetPassword");
  var resetPasswordForm = document.getElementById("resetPasswordForm");
  var resetPassword = document.getElementById("resetPassword");
  var resetNote = document.getElementById("resetNote");
  var msTitle = document.getElementById("msTitle");

  var currentSession = null;
  var currentNickname = null;
  var currentAvatarUrl = null;
  // 이메일의 "비밀번호 재설정" 링크를 타고 들어오면 Supabase가 PASSWORD_RECOVERY 이벤트를
  // 쏘는데, 그 순간엔 임시 세션이 있어 자칫 평소 로그인 상태로 오인해 그릴 수 있으므로
  // 새 비밀번호를 입력받는 화면으로 먼저 보내고 끝나면 정상 로그인 상태로 넘어간다.
  var inRecovery = false;

  function displayName() {
    if (currentNickname) return currentNickname;
    return currentSession && currentSession.user ? emailName(currentSession.user) : "";
  }

  function paintAccount() {
    if (inRecovery) {
      apLoggedOut.classList.add("hidden");
      apLoggedIn.classList.add("hidden");
      if (apResetPassword) apResetPassword.classList.remove("hidden");
      return;
    }
    if (apResetPassword) apResetPassword.classList.add("hidden");
    var loggedIn = !!(currentSession && currentSession.user);
    apLoggedOut.classList.toggle("hidden", loggedIn);
    apLoggedIn.classList.toggle("hidden", !loggedIn);
    if (loggedIn) {
      var name = displayName();
      apName.textContent = name;
      apEmail.textContent = currentSession.user.email || "";
      nickForm.classList.add("hidden");
      if (currentAvatarUrl) {
        apAvatarImg.src = currentAvatarUrl;
        apAvatarImg.classList.remove("hidden");
        apAvatarLetter.classList.add("hidden");
      } else {
        apAvatarImg.classList.add("hidden");
        apAvatarLetter.classList.remove("hidden");
        apAvatarLetter.textContent = name.slice(0, 1).toUpperCase();
      }
      if (msTitle) msTitle.textContent = name + "'s SPACE";
    } else if (msTitle) {
      msTitle.textContent = "MY SPACE";
    }
    paintFeedbackAuthState();
  }

  function loadProfile() {
    if (!currentSession || !currentSession.user) { currentNickname = null; currentAvatarUrl = null; return Promise.resolve(); }
    return sb.from("profiles").select("nickname, avatar_url").eq("id", currentSession.user.id).maybeSingle()
      .then(function (res) {
        currentNickname = (res.data && res.data.nickname) || null;
        currentAvatarUrl = (res.data && res.data.avatar_url) || null;
      })
      .catch(function () { currentNickname = null; currentAvatarUrl = null; });
  }

  if (apAvatar && apAvatarFile) {
    apAvatar.addEventListener("click", function () { apAvatarFile.click(); });
    apAvatarFile.addEventListener("change", function () {
      var file = apAvatarFile.files && apAvatarFile.files[0];
      apAvatarFile.value = "";
      if (!file || !currentSession || !currentSession.user) return;
      if (file.size > 3 * 1024 * 1024) {
        if (apAvatarNote) apAvatarNote.textContent = "3MB 이하 이미지만 가능합니다.";
        return;
      }
      var uid = currentSession.user.id;
      var ext = (file.name.split(".").pop() || "jpg").toLowerCase().replace(/[^a-z0-9]/g, "") || "jpg";
      var path = uid + "/avatar." + ext;
      if (apAvatarNote) apAvatarNote.textContent = "업로드 중…";
      sb.storage.from("avatars").upload(path, file, { upsert: true, cacheControl: "3600" })
        .then(function (res) {
          if (res.error) throw res.error;
          var pub = sb.storage.from("avatars").getPublicUrl(path);
          var url = pub.data.publicUrl + "?t=" + Date.now();
          return sb.from("profiles").upsert({ id: uid, avatar_url: url }).then(function (res2) {
            if (res2.error) throw res2.error;
            currentAvatarUrl = url;
            paintAccount();
            if (apAvatarNote) apAvatarNote.textContent = "";
          });
        })
        .catch(function (err) {
          if (apAvatarNote) apAvatarNote.textContent = "업로드 실패: " + (err && err.message ? err.message : err);
        });
    });
  }

  var AUTH_NOTE_DEFAULT = authNote ? authNote.textContent : "";
  function showAuthTab(tab) {
    var login = tab === "login";
    if (apTabLogin) apTabLogin.classList.toggle("is-on", login);
    if (apTabSignup) apTabSignup.classList.toggle("is-on", !login);
    if (loginForm) loginForm.classList.toggle("hidden", !login);
    if (signupForm) signupForm.classList.toggle("hidden", login);
    if (apForgotPw) apForgotPw.classList.toggle("hidden", !login);
    if (authNote) authNote.textContent = AUTH_NOTE_DEFAULT;
  }
  if (apTabLogin) apTabLogin.addEventListener("click", function () { showAuthTab("login"); });
  if (apTabSignup) apTabSignup.addEventListener("click", function () { showAuthTab("signup"); });

  function authFail(err) {
    var msg = (err && (err.message || err.error_description)) || String(err || "알 수 없는 오류");
    if (authNote) authNote.textContent = "오류: " + msg + " (다시 시도해주세요)";
  }
  // 네트워크가 끊기거나 요청이 어떤 이유로든 응답 없이 멈춰도 화면이 "…하는 중"에
  // 영원히 붙들려 있지 않도록, 일정 시간 안에 안 끝나면 타임아웃으로 대신 실패 처리한다.
  function withTimeout(promise, ms) {
    return new Promise(function (resolve, reject) {
      var t = setTimeout(function () { reject(new Error("응답이 없습니다. 잠시 후 다시 시도해주세요")); }, ms);
      promise.then(function (v) { clearTimeout(t); resolve(v); }, function (e) { clearTimeout(t); reject(e); });
    });
  }
  console.log("HEUY-DEBUG: loginForm element =", loginForm);
  if (loginForm) {
    loginForm.addEventListener("submit", function (e) {
      console.log("HEUY-DEBUG: login submit handler fired");
      e.preventDefault();
      var email = loginEmail.value.trim();
      var password = loginPassword.value;
      if (!email || !password) return;
      if (authNote) authNote.textContent = "로그인하는 중…";
      withTimeout(sb.auth.signInWithPassword({ email: email, password: password }), 15000).then(function (res) {
        if (res.error) { authFail(res.error); return; }
        loginPassword.value = "";
        // onAuthStateChange가 이 브라우저 환경에서 어떤 이유로든 늦게 오거나 안 올 수도
        // 있으니, 로그인 성공 직후 화면 전환을 여기서도 바로 한 번 확실히 해준다.
        currentSession = res.data && res.data.session;
        loadProfile().then(paintAccount);
      }).catch(authFail);
    });
  }
  if (signupForm) {
    signupForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var email = signupEmail.value.trim();
      var password = signupPassword.value;
      var nick = signupNick.value.trim();
      if (!email || !password) return;
      if (authNote) authNote.textContent = "가입하는 중…";
      withTimeout(sb.auth.signUp({ email: email, password: password }), 15000).then(function (res) {
        if (res.error) { authFail(res.error); return; }
        var user = res.data && res.data.user;
        var session = res.data && res.data.session;
        // 이메일 확인이 켜져 있는 프로젝트에서, 이미 가입된 이메일로 다시 가입하면
        // 에러 대신 identities가 빈 배열인 user를 그대로 돌려준다(이메일 열거 공격 방지용
        // Supabase 기본 동작) — 그대로 두면 "확인 메일을 보냈다"고 오해하게 되므로 구분한다.
        if (user && user.identities && user.identities.length === 0) {
          if (authNote) authNote.textContent = "이미 가입된 이메일입니다. 로그인해주세요.";
          showAuthTab("login");
          return;
        }
        var saveNick = (nick && user)
          ? sb.from("profiles").upsert({ id: user.id, nickname: nick }).catch(function () {})
          : Promise.resolve();
        return Promise.resolve(saveNick).then(function () {
          signupPassword.value = "";
          if (session) { // 이메일 확인이 꺼져 있으면 바로 로그인 세션이 생긴다
            currentSession = session;
            loadProfile().then(paintAccount);
            return;
          }
          if (authNote) authNote.textContent = email + " 로 확인 메일을 보냈습니다. 메일함에서 확인하면 가입이 끝나요.";
          showAuthTab("login");
        });
      }).catch(authFail);
    });
  }
  if (apForgotPw) {
    apForgotPw.addEventListener("click", function () {
      var email = (loginEmail && loginEmail.value || "").trim();
      if (!email) {
        if (authNote) authNote.textContent = "먼저 이메일을 입력해주세요.";
        if (loginEmail) loginEmail.focus();
        return;
      }
      if (authNote) authNote.textContent = "재설정 메일을 보내는 중…";
      withTimeout(sb.auth.resetPasswordForEmail(email, { redirectTo: window.location.href }), 15000)
        .then(function (res) {
          if (res.error) { authFail(res.error); return; }
          if (authNote) authNote.textContent = email + " 로 비밀번호 재설정 메일을 보냈습니다. 메일함을 확인하세요.";
        }).catch(authFail);
    });
  }
  if (resetPasswordForm) {
    resetPasswordForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var pw = resetPassword.value;
      if (!pw) return;
      if (resetNote) resetNote.textContent = "저장하는 중…";
      withTimeout(sb.auth.updateUser({ password: pw }), 15000).then(function (res) {
        if (res.error) { if (resetNote) resetNote.textContent = "오류: " + res.error.message; return; }
        resetPassword.value = "";
        inRecovery = false;
        loadProfile().then(paintAccount);
      }).catch(function (err) {
        if (resetNote) resetNote.textContent = "오류: " + (err && err.message ? err.message : err);
      });
    });
  }
  if (authLogout) {
    authLogout.addEventListener("click", function () { sb.auth.signOut(); });
  }
  if (apEditNick) {
    apEditNick.addEventListener("click", function () {
      nickInput.value = currentNickname || "";
      nickForm.classList.remove("hidden");
      nickInput.focus();
    });
  }
  if (nickCancel) {
    nickCancel.addEventListener("click", function () { nickForm.classList.add("hidden"); });
  }
  if (nickForm) {
    nickForm.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!currentSession || !currentSession.user) return;
      var nick = nickInput.value.trim();
      if (!nick) return;
      sb.from("profiles").upsert({ id: currentSession.user.id, nickname: nick }).then(function (res) {
        if (res.error) { alert("닉네임을 저장하지 못했습니다: " + res.error.message); return; }
        currentNickname = nick;
        paintAccount();
      });
    });
  }

  sb.auth.getSession().then(function (res) {
    currentSession = res.data && res.data.session;
    loadProfile().then(paintAccount);
  });
  sb.auth.onAuthStateChange(function (event, session) {
    currentSession = session;
    if (event === "PASSWORD_RECOVERY") inRecovery = true;
    loadProfile().then(paintAccount);
  });

  // ---------------------------------------------------------- 피드백 채팅방
  var room = document.getElementById("feedbackRoom");
  var messages, form, input, submitBtn, hint, loginLink;
  var paintFeedbackAuthState = function () {};

  if (room) {
    messages = document.getElementById("frMessages");
    form = document.getElementById("frForm");
    input = document.getElementById("frInput");
    submitBtn = document.getElementById("frSubmit");
    hint = document.getElementById("frHint");
    loginLink = document.getElementById("frLoginLink");

    paintFeedbackAuthState = function () {
      var loggedIn = !!(currentSession && currentSession.user);
      input.disabled = !loggedIn;
      submitBtn.disabled = !loggedIn;
      input.placeholder = loggedIn ? "댓글을 남겨보세요…" : "로그인하면 댓글을 남길 수 있어요";
      hint.classList.toggle("hidden", loggedIn);
    };

    if (loginLink && loginEmail) {
      loginLink.addEventListener("click", function () {
        showAuthTab("login");
        loginEmail.focus();
        panel.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    }

    var renderMessage = function (row) {
      var el = document.createElement("div");
      el.className = "fr-msg";
      el.innerHTML =
        '<span class="fr-name">' + esc(row.display_name) + '</span>' +
        '<span class="fr-time">' + esc(fmtTime(row.created_at)) + '</span>' +
        '<p class="fr-body"></p>';
      el.querySelector(".fr-body").textContent = row.body;
      messages.appendChild(el);
    };
    var scrollToBottom = function () { messages.scrollTop = messages.scrollHeight; };

    sb.from("feedback_comments").select("*").order("created_at", { ascending: true }).limit(300)
      .then(function (res) {
        messages.innerHTML = "";
        if (res.error) { messages.innerHTML = '<p class="fr-empty">댓글을 불러오지 못했습니다.</p>'; return; }
        if (!res.data.length) { messages.innerHTML = '<p class="fr-empty">아직 댓글이 없습니다. 첫 댓글을 남겨보세요.</p>'; return; }
        res.data.forEach(renderMessage);
        scrollToBottom();
      });

    sb.channel("feedback_comments_live")
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "feedback_comments" },
        function (payload) {
          var empty = messages.querySelector(".fr-empty");
          if (empty) empty.remove();
          var wasAtBottom = messages.scrollHeight - messages.scrollTop - messages.clientHeight < 40;
          renderMessage(payload.new);
          if (wasAtBottom) scrollToBottom();
        })
      .subscribe();

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!currentSession || !currentSession.user) return;
      var body = input.value.trim();
      if (!body) return;
      submitBtn.disabled = true;
      sb.from("feedback_comments").insert({
        user_id: currentSession.user.id,
        display_name: displayName(),
        body: body
      }).then(function (res) {
        submitBtn.disabled = false;
        if (res.error) alert("댓글을 남기지 못했습니다: " + res.error.message);
        else input.value = "";
      });
    });
  }
  console.log("HEUY-DEBUG: account panel init finished OK");
  } catch (err) {
    console.error("HEUY-DEBUG: account panel init CRASHED:", err);
  }
})();

/* HEUY.ARCHI — 관리자 대시보드 (admin.html 전용)
   접근 통제는 이 스크립트가 아니라 Supabase RLS가 한다: 관리자가 아니면 profiles.is_admin
   조회 자체가 false로 돌아오고, 방문자·유저 쿼리도 정책에 막혀 빈 값만 온다. */
(function () {
  "use strict";
  var gate = document.getElementById("adminGate");
  if (!gate) return;
  var sb = heuySupabase();
  if (!sb) { gate.textContent = "로그인 모듈을 불러오지 못했습니다."; return; }

  var denied = document.getElementById("adminDenied");
  var dash = document.getElementById("adminDash");
  // 홈페이지에 끼워 넣은 버전(admin.html이 아니라)에만 있는 바깥 래퍼. 방문자 전원이
  // 보는 자리라 관리자가 아니면 '거부됨' 문구 없이 통째로 숨어 있어야 한다.
  var homeWrap = document.getElementById("adminHomePanel");
  function showDenied() {
    if (homeWrap) return; // 홈페이지에서는 조용히 숨어만 있는다
    if (denied) denied.classList.remove("hidden");
  }
  var avToday = document.getElementById("avToday");
  var avWeek = document.getElementById("avWeek");
  var avTotal = document.getElementById("avTotal");
  var trendEl = document.getElementById("adminVisitTrend");
  var rowsEl = document.getElementById("adminUserRows");

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function kstDay(d) {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit"
    }).format(d);
  }
  function dayBoundsISO(dayStr) {
    var start = dayStr + "T00:00:00+09:00";
    var end = new Date(new Date(start).getTime() + 86400000).toISOString();
    return { start: start, end: end };
  }

  function loadVisitorStats() {
    var today = kstDay(new Date());
    var todayB = dayBoundsISO(today);
    var weekStartDay = kstDay(new Date(Date.now() - 6 * 86400000)); // 오늘 포함 7일
    var weekB = dayBoundsISO(weekStartDay);

    sb.from("page_views").select("*", { count: "exact", head: true })
      .gte("visited_at", todayB.start).lt("visited_at", todayB.end)
      .then(function (res) { if (avToday) avToday.textContent = (res.count || 0).toLocaleString(); });

    sb.from("page_views").select("*", { count: "exact", head: true })
      .then(function (res) { if (avTotal) avTotal.textContent = (res.count || 0).toLocaleString(); });

    sb.from("page_views").select("visited_at").gte("visited_at", weekB.start)
      .then(function (res) {
        var rows = res.data || [];
        if (avWeek) avWeek.textContent = rows.length.toLocaleString();
        var byDay = {};
        rows.forEach(function (r) {
          var d = kstDay(new Date(r.visited_at));
          byDay[d] = (byDay[d] || 0) + 1;
        });
        var days = [];
        for (var i = 6; i >= 0; i--) {
          var d = kstDay(new Date(Date.now() - i * 86400000));
          days.push([d, byDay[d] || 0]);
        }
        var top = 1;
        days.forEach(function (x) { if (x[1] > top) top = x[1]; });
        if (trendEl) {
          trendEl.innerHTML = days.map(function (x) {
            var pct = (x[1] / top * 100).toFixed(1);
            return '<li class="st-bar"><span class="st-bl">' + esc(x[0].slice(5)) + '</span>'
              + '<span class="st-btrack"><span class="st-bfill" style="width:' + pct + '%"></span></span>'
              + '<span class="st-bv">' + x[1] + '<i>회</i></span></li>';
          }).join("");
        }
      });
  }

  function toggleFlag(btn, field) {
    var tr = btn.closest("tr");
    var id = tr.getAttribute("data-id");
    var next = !btn.classList.contains("is-on");
    btn.disabled = true;
    var patch = { id: id };
    patch[field] = next;
    sb.from("profiles").upsert(patch).then(function (res) {
      btn.disabled = false;
      if (res.error) { alert("변경하지 못했습니다: " + res.error.message); return; }
      btn.classList.toggle("is-on", next);
      if (field === "is_admin") btn.textContent = next ? "관리자" : "-";
      if (field === "is_banned") btn.textContent = next ? "정지됨" : "정상";
    });
  }

  function loadUsers(myId) {
    if (!rowsEl) return;
    Promise.all([
      sb.from("admin_user_emails").select("id, email, created_at"),
      sb.from("profiles").select("id, nickname, is_admin, is_banned")
    ]).then(function (res) {
      var emails = res[0].data || [];
      var profiles = {};
      (res[1].data || []).forEach(function (p) { profiles[p.id] = p; });
      var users = emails.map(function (e) {
        var p = profiles[e.id] || {};
        return {
          id: e.id, email: e.email, created_at: e.created_at,
          nickname: p.nickname || (e.email || "").split("@")[0],
          is_admin: !!p.is_admin, is_banned: !!p.is_banned
        };
      }).sort(function (a, b) { return (b.created_at || "").localeCompare(a.created_at || ""); });

      if (!users.length) { rowsEl.innerHTML = '<tr><td colspan="5">아직 없습니다.</td></tr>'; return; }
      rowsEl.innerHTML = users.map(function (u) {
        var joined = u.created_at ? String(u.created_at).slice(0, 10) : "-";
        var selfAttr = u.id === myId ? ' disabled title="본인 계정은 여기서 바꿀 수 없습니다"' : "";
        return '<tr data-id="' + esc(u.id) + '">'
          + '<td>' + esc(u.nickname) + '</td>'
          + '<td class="admin-email">' + esc(u.email || "-") + '</td>'
          + '<td>' + esc(joined) + '</td>'
          + '<td><button type="button" class="admin-toggle admin-toggle-admin' + (u.is_admin ? " is-on" : "") + '"' + selfAttr + '>'
          + (u.is_admin ? "관리자" : "-") + '</button></td>'
          + '<td><button type="button" class="admin-toggle admin-toggle-ban' + (u.is_banned ? " is-on" : "") + '"' + selfAttr + '>'
          + (u.is_banned ? "정지됨" : "정상") + '</button></td>'
          + '</tr>';
      }).join("");

      var adminBtns = rowsEl.querySelectorAll(".admin-toggle-admin");
      for (var i = 0; i < adminBtns.length; i++) {
        adminBtns[i].addEventListener("click", (function (btn) {
          return function () { toggleFlag(btn, "is_admin"); };
        })(adminBtns[i]));
      }
      var banBtns = rowsEl.querySelectorAll(".admin-toggle-ban");
      for (var j = 0; j < banBtns.length; j++) {
        banBtns[j].addEventListener("click", (function (btn) {
          return function () { toggleFlag(btn, "is_banned"); };
        })(banBtns[j]));
      }
    });
  }

  sb.auth.getSession().then(function (res) {
    var session = res.data && res.data.session;
    if (!session || !session.user) {
      gate.classList.add("hidden");
      showDenied();
      return;
    }
    sb.from("profiles").select("is_admin").eq("id", session.user.id).maybeSingle().then(function (r) {
      gate.classList.add("hidden");
      if (!r.data || !r.data.is_admin) { showDenied(); return; }
      if (homeWrap) homeWrap.classList.remove("hidden");
      if (dash) dash.classList.remove("hidden");
      loadVisitorStats();
      loadUsers(session.user.id);
    });
  }).catch(function () {
    gate.classList.add("hidden");
    showDenied();
  });
})();
