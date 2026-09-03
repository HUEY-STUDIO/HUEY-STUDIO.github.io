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

  var currentSession = null;
  var currentNickname = null;

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
      apAvatar.textContent = name.slice(0, 1).toUpperCase();
      apEmail.textContent = currentSession.user.email || "";
      nickForm.classList.add("hidden");
    }
    paintFeedbackAuthState();
  }

  function loadProfile() {
    if (!currentSession || !currentSession.user) { currentNickname = null; return Promise.resolve(); }
    return sb.from("profiles").select("nickname").eq("id", currentSession.user.id).maybeSingle()
      .then(function (res) {
        currentNickname = (res.data && res.data.nickname) || null;
      })
      .catch(function () { currentNickname = null; });
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
