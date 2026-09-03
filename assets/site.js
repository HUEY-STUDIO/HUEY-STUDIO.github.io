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

/* 미니 스페이스 — 계정 패널 아래 붙는 장식용 방. 방향키로 픽셀 캐릭터를 자유롭게(대각선 포함)
   부드럽게 움직인다. 로그인 여부와 무관하게 동작하고, 위치는 저장하지 않는다(그냥 놀이용).

   진짜 3D 회전(rotateX/rotateZ) 대신 고전적인 2:1 아이소메트릭 투영을 쓴다 — 좌표를
   화면 다이아몬드로 매핑만 하는 방식이라 박스섀도 픽셀아트가 회전으로 흐려지지 않고
   또렷하게 남는다. 여기 ISO_* 상수는 assets/style.css 의 .ms-platform/.ms-floor
   치수(220×110)와 맞물려 있으니 같이 바꿔야 한다. */
(function () {
  "use strict";
  var room = document.getElementById("msRoom");
  var platform = document.querySelector(".ms-platform");
  var char = document.getElementById("msChar");
  if (!room || !platform || !char) return;

  var WORLD_MAX = 10;              // gx, gy 범위 [0, WORLD_MAX]
  var ISO_ORIGIN_X = 110, ISO_ORIGIN_Y = 0;   // .ms-platform 폭 220 / 높이 110의 꼭짓점
  var ISO_TW = 11, ISO_TH = 5.5;    // (220/2)/WORLD_MAX, (110/2)/WORLD_MAX
  var CHAR_W = 20, CHAR_H = 28, FOOT_OFFSET = 24; // 캐릭터 "발"이 투영점에 오도록

  var gx = WORLD_MAX / 2, gy = WORLD_MAX / 2;

  function project(px, py) {
    return {
      x: ISO_ORIGIN_X + (px - py) * ISO_TW,
      y: ISO_ORIGIN_Y + (px + py) * ISO_TH
    };
  }
  function paint() {
    var p = project(gx, gy);
    char.style.left = (p.x - CHAR_W / 2) + "px";
    char.style.top = (p.y - FOOT_OFFSET) + "px";
  }
  paint();

  // 화면에서 위/아래/좌/우로 보이도록, 각 방향키를 월드 대각선 한 쌍에 대응시킨다
  // (아이소메트릭 게임의 표준 방식) — 여러 키를 같이 누르면 자연히 나머지 4방향도 나온다.
  var keys = Object.create(null);
  var DIRS = {
    ArrowUp: [-1, -1], ArrowDown: [1, 1],
    ArrowLeft: [-1, 1], ArrowRight: [1, -1]
  };
  var SPEED = 3.2; // 초당 월드유닛
  var rafId = null, lastT = null;

  function clampWorld(v) { return Math.max(0, Math.min(WORLD_MAX, v)); }

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
      rafId = requestAnimationFrame(tick);
    } else {
      rafId = null; lastT = null;
    }
  }
  function ensureLoop() {
    if (rafId == null) rafId = requestAnimationFrame(tick);
  }
  function anyKeyHeld() {
    for (var k in DIRS) if (keys[k]) return true;
    return false;
  }

  room.addEventListener("keydown", function (e) {
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
})();

/* HEUY.ARCHI — 로그인(매직링크) + 닉네임 + 홈페이지 피드백/댓글 채팅방
   Supabase Auth + Postgres + Realtime. 계정 패널·피드백방 모두 홈페이지 전용이라
   #accountPanel 이 없는 페이지(지난호·카테고리 등)에서는 이 스크립트가 아무 일도 안 한다. */
(function () {
  "use strict";
  var panel = document.getElementById("accountPanel");
  if (!panel) return;
  if (!window.supabase || !window.supabase.createClient) return;

  var SUPABASE_URL = "https://rwmivexpkjppvsvwuguw.supabase.co";
  var SUPABASE_KEY = "sb_publishable_iDTkwOY5Qo42G0xj7Igqaw_rgfrWMyH";
  var sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

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
  var authForm = document.getElementById("authForm");
  var authEmail = document.getElementById("authEmail");
  var authNote = document.getElementById("authNote");
  var msTitle = document.getElementById("msTitle");

  var currentSession = null;
  var currentNickname = null;
  var currentAvatarUrl = null;

  function displayName() {
    if (currentNickname) return currentNickname;
    return currentSession && currentSession.user ? emailName(currentSession.user) : "";
  }

  function paintAccount() {
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

  if (authForm) {
    authForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var email = authEmail.value.trim();
      if (!email) return;
      authNote.textContent = "보내는 중…";
      sb.auth.signInWithOtp({
        email: email,
        options: { emailRedirectTo: window.location.href }
      }).then(function (res) {
        authNote.textContent = res.error
          ? "오류: " + res.error.message
          : email + " 로 로그인 링크를 보냈습니다. 메일함을 확인하세요.";
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
  sb.auth.onAuthStateChange(function (_event, session) {
    currentSession = session;
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

    if (loginLink && authEmail) {
      loginLink.addEventListener("click", function () {
        authEmail.focus();
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
})();
