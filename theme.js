// Explicit light/dark toggle, shared by index.html and login.html.
// Falls back to the OS preference until the visitor picks one.

const THEME_KEY = "glowup_theme_v1";

function readStoredTheme() {
  try { return localStorage.getItem(THEME_KEY); } catch (e) { return null; }
}

function writeStoredTheme(theme) {
  try { localStorage.setItem(THEME_KEY, theme); } catch (e) {}
}

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  var btn = document.getElementById("themeToggle");
  if (btn) {
    btn.setAttribute("data-mode", theme);
    btn.setAttribute("aria-label", theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
  }
}

export function initTheme() {
  var saved = readStoredTheme();
  var theme = saved || (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  applyTheme(theme);

  var btn = document.getElementById("themeToggle");
  if (btn) {
    btn.addEventListener("click", function () {
      var current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
      var next = current === "dark" ? "light" : "dark";
      applyTheme(next);
      writeStoredTheme(next);
    });
  }
}
