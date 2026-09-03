(function () {
  "use strict";

  /* ---------- Mobile nav ---------- */
  var navToggle = document.getElementById("navToggle");
  var navLinks = document.getElementById("navLinks");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      var open = navLinks.classList.toggle("open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    navLinks.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        navLinks.classList.remove("open");
        navToggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  /* ---------- FAQ accordion ---------- */
  document.querySelectorAll(".faq-item").forEach(function (item) {
    var btn = item.querySelector(".faq-question");
    btn.addEventListener("click", function () {
      item.classList.toggle("open");
    });
  });

  /* ---------- Glow-Up Assessment quiz ---------- */
  var QUIZ_STORAGE_KEY = "glowup_quiz_result_v1";
  var questions = document.querySelectorAll(".quiz-question");
  var progressDots = document.querySelectorAll("#quizProgress .dot");
  var resultPanel = document.getElementById("quizResult");
  var questionsWrap = document.getElementById("quizQuestions");
  var resultList = document.getElementById("resultList");
  var retakeBtn = document.getElementById("retakeQuiz");

  var answers = {};
  var currentQuestion = 0;

  // Priority actions the quiz can recommend, each mapped to a guide section.
  var actions = {
    skinOily: { text: "Switch to a 0.5–2% salicylic acid cleanser to clear pores before breakouts start.", href: "#skincare", label: "Jump to Skincare" },
    skinDry: { text: "Add a ceramide + niacinamide moisturizer within 60 seconds of washing your face.", href: "#skincare", label: "Jump to Skincare" },
    sunscreen: { text: "Apply a full 1/4 teaspoon of SPF 30+ to your face every morning — most people use half enough.", href: "#skincare", label: "Jump to Skincare" },
    posture: { text: "Start Wall Angels (3x10) and Chin Tucks (3x10) daily to fix forward-head posture.", href: "#fitness", label: "Jump to Posture & Fitness" },
    reset90: { text: "Set a 90-minute timer to stand and do a 30-second doorway chest stretch.", href: "#fitness", label: "Jump to Posture & Fitness" },
    grooming: { text: "Fix your eyebrow shape and beard/neckline using the exact anatomy rules in Grooming.", href: "#grooming", label: "Jump to Grooming" },
    dental: { text: "Dial in 2-minute, twice-daily brushing at a 45° angle — the highest-leverage grooming habit.", href: "#grooming", label: "Jump to Grooming" },
    sleep: { text: "Target sleep in full 90-minute cycles (7.5 or 9 hours) instead of a flat 8-hour target.", href: "#lifestyle", label: "Jump to Lifestyle" },
    water: { text: "Calculate your real water target: bodyweight (lbs) ÷ 2 = ounces per day, spread through the day.", href: "#lifestyle", label: "Jump to Lifestyle" },
    puffiness: { text: "Cut evening sodium/alcohol and try sleeping on your back to reduce morning facial puffiness.", href: "#face", label: "Jump to Face & Jawline" }
  };

  function setupQuizButtons() {
    document.querySelectorAll(".quiz-options").forEach(function (group) {
      var key = group.getAttribute("data-key");
      group.querySelectorAll("button").forEach(function (btn) {
        btn.addEventListener("click", function () {
          answers[key] = btn.getAttribute("data-value");
          goToNextQuestion();
        });
      });
    });
  }

  function goToNextQuestion() {
    if (progressDots[currentQuestion]) {
      progressDots[currentQuestion].classList.remove("active");
      progressDots[currentQuestion].classList.add("done");
    }
    currentQuestion++;
    if (currentQuestion < questions.length) {
      questions.forEach(function (q, i) {
        q.classList.toggle("hidden", i !== currentQuestion);
      });
      if (progressDots[currentQuestion]) {
        progressDots[currentQuestion].classList.add("active");
      }
    } else {
      finishQuiz();
    }
  }

  function computePriorityStack() {
    var stack = [];

    // Concern picked is always the top priority.
    var concernMap = {
      skin: answers.skin === "dry" ? actions.skinDry : actions.skinOily,
      posture: actions.posture,
      grooming: actions.grooming,
      energy: actions.sleep
    };
    if (answers.concern && concernMap[answers.concern]) {
      stack.push(concernMap[answers.concern]);
    }

    if (answers.sleep === "low" && stack.indexOf(actions.sleep) === -1) {
      stack.push(actions.sleep);
    }
    if (answers.water === "low" || answers.water === "unsure") {
      stack.push(actions.water);
    }
    if (answers.skin === "oily" && stack.indexOf(actions.skinOily) === -1) {
      stack.push(actions.skinOily);
    }
    if (answers.skin === "dry" && stack.indexOf(actions.skinDry) === -1) {
      stack.push(actions.skinDry);
    }

    // Fill remaining slots with generally high-impact actions not already included.
    var fillers = [actions.sunscreen, actions.reset90, actions.dental, actions.puffiness];
    for (var i = 0; i < fillers.length && stack.length < 3; i++) {
      if (stack.indexOf(fillers[i]) === -1) stack.push(fillers[i]);
    }

    return stack.slice(0, 3);
  }

  function renderResult(stack) {
    resultList.innerHTML = "";
    stack.forEach(function (item, i) {
      var li = document.createElement("li");
      li.innerHTML =
        "<strong>" + (i + 1) + ". " + item.text + "</strong>" +
        '<a href="' + item.href + '">' + item.label + " →</a>";
      resultList.appendChild(li);
    });
    questionsWrap.classList.add("hidden");
    resultPanel.classList.remove("hidden");
  }

  function finishQuiz() {
    var stack = computePriorityStack();
    try {
      localStorage.setItem(QUIZ_STORAGE_KEY, JSON.stringify({ answers: answers, stack: stack }));
    } catch (e) { /* localStorage unavailable, skip persistence */ }
    renderResult(stack);
  }

  function resetQuiz(showQuestions) {
    answers = {};
    currentQuestion = 0;
    questions.forEach(function (q, i) { q.classList.toggle("hidden", i !== 0); });
    progressDots.forEach(function (d, i) {
      d.classList.remove("done");
      d.classList.toggle("active", i === 0);
    });
    resultPanel.classList.add("hidden");
    if (showQuestions !== false) questionsWrap.classList.remove("hidden");
  }

  function loadSavedQuiz() {
    try {
      var raw = localStorage.getItem(QUIZ_STORAGE_KEY);
      if (!raw) return false;
      var saved = JSON.parse(raw);
      if (!saved || !saved.stack || !saved.stack.length) return false;
      renderResult(saved.stack);
      return true;
    } catch (e) {
      return false;
    }
  }

  if (questionsWrap && resultPanel) {
    setupQuizButtons();
    if (progressDots[0]) progressDots[0].classList.add("active");
    if (!loadSavedQuiz()) {
      // fresh visitor: quiz already showing by default
    }
    if (retakeBtn) {
      retakeBtn.addEventListener("click", function () {
        try { localStorage.removeItem(QUIZ_STORAGE_KEY); } catch (e) {}
        resetQuiz(true);
      });
    }
  }

  /* ---------- Daily routine checklist + streak ---------- */
  var ROUTINE_STATE_KEY = "glowup_routine_state_v1";
  var STREAK_KEY = "glowup_streak_v1";

  var habits = [
    "Cleanse with the right active (AM & PM)",
    "Apply sunscreen — a full 1/4 teaspoon",
    "Moisturize while skin is still damp",
    "Wall Angels + Chin Tucks (3x10 each)",
    "90-minute posture reset stretch",
    "Hit your water target for the day",
    "Brush 2 min, floss once, 45° angle",
    "5-minute box breathing reset"
  ];

  var routineList = document.getElementById("routineList");
  var progressFill = document.getElementById("progressFill");
  var progressLabel = document.getElementById("progressLabel");
  var resetRoutineBtn = document.getElementById("resetRoutine");
  var streakBadge = document.getElementById("streakBadge");

  function todayKey() {
    var d = new Date();
    return d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate();
  }

  function readJSON(key, fallback) {
    try {
      var raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      return fallback;
    }
  }

  function writeJSON(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {}
  }

  function getTodayState() {
    var all = readJSON(ROUTINE_STATE_KEY, {});
    return all[todayKey()] || {};
  }

  function setTodayState(state) {
    var all = readJSON(ROUTINE_STATE_KEY, {});
    all[todayKey()] = state;
    writeJSON(ROUTINE_STATE_KEY, all);
  }

  function updateStreak(hasCheckedToday) {
    var streak = readJSON(STREAK_KEY, { count: 0, lastDate: null });
    var today = todayKey();

    if (streak.lastDate === today) {
      // already counted today
    } else if (hasCheckedToday) {
      var yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      var yKey = yesterday.getFullYear() + "-" + (yesterday.getMonth() + 1) + "-" + yesterday.getDate();
      streak.count = streak.lastDate === yKey ? streak.count + 1 : 1;
      streak.lastDate = today;
      writeJSON(STREAK_KEY, streak);
    }
    if (streakBadge) {
      streakBadge.textContent = "🔥 " + streak.count + "-day streak";
    }
  }

  function renderRoutine() {
    if (!routineList) return;
    var state = getTodayState();
    routineList.innerHTML = "";

    habits.forEach(function (habit, i) {
      var li = document.createElement("li");
      var checked = !!state[i];
      if (checked) li.classList.add("checked");

      var checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.id = "habit-" + i;
      checkbox.checked = checked;

      var label = document.createElement("label");
      label.setAttribute("for", "habit-" + i);
      label.style.display = "flex";
      label.style.alignItems = "center";
      label.style.gap = "0.6rem";
      label.style.width = "100%";
      label.style.cursor = "pointer";

      var span = document.createElement("span");
      span.textContent = habit;

      checkbox.addEventListener("change", function () {
        var s = getTodayState();
        s[i] = checkbox.checked;
        setTodayState(s);
        li.classList.toggle("checked", checkbox.checked);
        updateProgress();
        updateStreak(Object.keys(s).some(function (k) { return s[k]; }));
      });

      label.appendChild(checkbox);
      label.appendChild(span);
      li.appendChild(label);
      routineList.appendChild(li);
    });

    updateProgress();
    var anyChecked = Object.keys(state).some(function (k) { return state[k]; });
    updateStreak(anyChecked);
  }

  function updateProgress() {
    var state = getTodayState();
    var done = habits.reduce(function (sum, _, i) { return sum + (state[i] ? 1 : 0); }, 0);
    var pct = habits.length ? Math.round((done / habits.length) * 100) : 0;
    if (progressFill) progressFill.style.width = pct + "%";
    if (progressLabel) progressLabel.textContent = done + " / " + habits.length + " done today";
  }

  if (resetRoutineBtn) {
    resetRoutineBtn.addEventListener("click", function () {
      setTodayState({});
      renderRoutine();
    });
  }

  renderRoutine();
})();
