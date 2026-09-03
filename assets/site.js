/* HEUY.ARCHI — 로그인(매직링크) + 홈페이지 피드백/댓글 채팅방
   Supabase Auth + Realtime. 이 파일은 모든 페이지에서 로드되며,
   #feedbackRoom 요소가 있는 페이지(홈페이지)에서만 채팅방을 그린다. */
(function () {
  "use strict";
  if (!window.supabase || !window.supabase.createClient) return;

  var SUPABASE_URL = "https://rwmivexpkjppvsvwuguw.supabase.co";
  var SUPABASE_KEY = "sb_publishable_iDTkwOY5Qo42G0xj7Igqaw_rgfrWMyH";
  var sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function displayName(user) {
    if (!user) return "";
    return (user.email || "익명").split("@")[0];
  }
  function fmtTime(iso) {
    var d = new Date(iso);
    var now = new Date();
    var sameDay = d.toDateString() === now.toDateString();
    var hh = ("0" + d.getHours()).slice(-2), mm = ("0" + d.getMinutes()).slice(-2);
    if (sameDay) return hh + ":" + mm;
    return (d.getMonth() + 1) + "." + d.getDate() + " " + hh + ":" + mm;
  }

  // ---------------------------------------------------------- 로그인 UI (전체 페이지 공통)
  var authBtn = document.getElementById("authBtn");
  var authPop = document.getElementById("authPop");
  var authForm = document.getElementById("authForm");
  var authEmail = document.getElementById("authEmail");
  var authNote = document.getElementById("authNote");
  var authLoggedOut = document.getElementById("authLoggedOut");
  var authLoggedIn = document.getElementById("authLoggedIn");
  var authUserName = document.getElementById("authUserName");
  var authLogout = document.getElementById("authLogout");

  var currentSession = null;
  var paintFeedbackAuthState = function () {}; // #feedbackRoom 이 있는 페이지에서만 아래에서 재정의된다

  function paintAuth(session) {
    currentSession = session;
    if (!authBtn) return;
    if (session && session.user) {
      authBtn.textContent = displayName(session.user) + "님 ▾";
      authBtn.classList.add("is-in");
      if (authLoggedOut) authLoggedOut.classList.add("hidden");
      if (authLoggedIn) authLoggedIn.classList.remove("hidden");
      if (authUserName) authUserName.textContent = session.user.email || "";
    } else {
      authBtn.textContent = "로그인";
      authBtn.classList.remove("is-in");
      if (authLoggedOut) authLoggedOut.classList.remove("hidden");
      if (authLoggedIn) authLoggedIn.classList.add("hidden");
    }
    paintFeedbackAuthState(session);
  }

  if (authBtn && authPop) {
    authBtn.addEventListener("click", function () {
      authPop.classList.toggle("hidden");
    });
    document.addEventListener("click", function (e) {
      if (!authPop.contains(e.target) && e.target !== authBtn) {
        authPop.classList.add("hidden");
      }
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
        if (res.error) {
          authNote.textContent = "오류: " + res.error.message;
        } else {
          authNote.textContent = email + " 로 로그인 링크를 보냈습니다. 메일함을 확인하세요.";
        }
      });
    });
  }
  if (authLogout) {
    authLogout.addEventListener("click", function () {
      sb.auth.signOut();
      if (authPop) authPop.classList.add("hidden");
    });
  }

  sb.auth.getSession().then(function (res) {
    paintAuth(res.data && res.data.session);
  });
  sb.auth.onAuthStateChange(function (_event, session) {
    paintAuth(session);
  });

  // ---------------------------------------------------------- 피드백 채팅방 (홈페이지 전용)
  var room = document.getElementById("feedbackRoom");
  if (!room) return;

  var messages = document.getElementById("frMessages");
  var form = document.getElementById("frForm");
  var input = document.getElementById("frInput");
  var submitBtn = document.getElementById("frSubmit");
  var hint = document.getElementById("frHint");
  var loginLink = document.getElementById("frLoginLink");

  paintFeedbackAuthState = function (session) {
    if (!form) return;
    var loggedIn = !!(session && session.user);
    input.disabled = !loggedIn;
    submitBtn.disabled = !loggedIn;
    input.placeholder = loggedIn ? "댓글을 남겨보세요…" : "로그인하면 댓글을 남길 수 있어요";
    if (hint) hint.classList.toggle("hidden", loggedIn);
  };
  paintFeedbackAuthState(currentSession);

  if (loginLink && authBtn) {
    loginLink.addEventListener("click", function () {
      authBtn.click();
      authEmail && authEmail.focus();
    });
  }

  function renderMessage(row, atBottom) {
    var el = document.createElement("div");
    el.className = "fr-msg";
    el.dataset.id = row.id;
    el.innerHTML =
      '<span class="fr-name">' + esc(row.display_name) + '</span>' +
      '<span class="fr-time">' + esc(fmtTime(row.created_at)) + '</span>' +
      '<p class="fr-body"></p>';
    el.querySelector(".fr-body").textContent = row.body;
    if (atBottom) messages.appendChild(el); else messages.insertBefore(el, messages.firstChild);
    return el;
  }

  function scrollToBottom() {
    messages.scrollTop = messages.scrollHeight;
  }

  sb.from("feedback_comments")
    .select("*")
    .order("created_at", { ascending: true })
    .limit(300)
    .then(function (res) {
      messages.innerHTML = "";
      if (res.error) {
        messages.innerHTML = '<p class="fr-empty">댓글을 불러오지 못했습니다.</p>';
        return;
      }
      if (!res.data.length) {
        messages.innerHTML = '<p class="fr-empty">아직 댓글이 없습니다. 첫 댓글을 남겨보세요.</p>';
      } else {
        res.data.forEach(function (row) { renderMessage(row, true); });
        scrollToBottom();
      }
    });

  sb.channel("feedback_comments_live")
    .on("postgres_changes",
      { event: "INSERT", schema: "public", table: "feedback_comments" },
      function (payload) {
        var empty = messages.querySelector(".fr-empty");
        if (empty) empty.remove();
        var wasAtBottom = messages.scrollHeight - messages.scrollTop - messages.clientHeight < 40;
        renderMessage(payload.new, true);
        if (wasAtBottom) scrollToBottom();
      })
    .subscribe();

  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!currentSession || !currentSession.user) return;
      var body = input.value.trim();
      if (!body) return;
      submitBtn.disabled = true;
      sb.from("feedback_comments").insert({
        user_id: currentSession.user.id,
        display_name: displayName(currentSession.user),
        body: body
      }).then(function (res) {
        submitBtn.disabled = false;
        if (res.error) {
          alert("댓글을 남기지 못했습니다: " + res.error.message);
        } else {
          input.value = "";
        }
      });
    });
  }
})();
