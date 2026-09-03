import {
  isBackendConfigured,
  onAuthChange,
  signIn,
  signUp,
  signOutUser,
  resetPassword
} from "./auth.js";
import { initTheme } from "./theme.js";

initTheme();

const authCard = document.getElementById("authCard");
const authTabs = document.getElementById("authTabs");
const signinForm = document.getElementById("signinForm");
const signupForm = document.getElementById("signupForm");
const authMessage = document.getElementById("authMessage");
const authSignedIn = document.getElementById("authSignedIn");
const authNotConfigured = document.getElementById("authNotConfigured");
const signedInEmail = document.getElementById("signedInEmail");
const signOutBtn = document.getElementById("signOutBtn");
const forgotPasswordBtn = document.getElementById("forgotPasswordBtn");

function showMessage(text, isError) {
  authMessage.textContent = text;
  authMessage.classList.remove("hidden");
  authMessage.classList.toggle("auth-message-error", !!isError);
}

function clearMessage() {
  authMessage.classList.add("hidden");
  authMessage.textContent = "";
}

if (authTabs) {
  authTabs.querySelectorAll(".auth-tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      authTabs.querySelectorAll(".auth-tab").forEach(function (t) { t.classList.remove("active"); });
      tab.classList.add("active");
      var isSignup = tab.getAttribute("data-tab") === "signup";
      signinForm.classList.toggle("hidden", isSignup);
      signupForm.classList.toggle("hidden", !isSignup);
      clearMessage();
    });
  });
}

if (signinForm) {
  signinForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    clearMessage();
    var email = document.getElementById("signinEmail").value.trim();
    var password = document.getElementById("signinPassword").value;
    try {
      await signIn(email, password);
    } catch (err) {
      showMessage(friendlyError(err), true);
    }
  });
}

if (signupForm) {
  signupForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    clearMessage();
    var email = document.getElementById("signupEmail").value.trim();
    var password = document.getElementById("signupPassword").value;
    try {
      await signUp(email, password);
    } catch (err) {
      showMessage(friendlyError(err), true);
    }
  });
}

if (forgotPasswordBtn) {
  forgotPasswordBtn.addEventListener("click", async function () {
    var email = document.getElementById("signinEmail").value.trim();
    if (!email) {
      showMessage("Enter your email above first, then click \"Forgot password?\" again.", true);
      return;
    }
    try {
      await resetPassword(email);
      showMessage("Password reset email sent — check your inbox.", false);
    } catch (err) {
      showMessage(friendlyError(err), true);
    }
  });
}

if (signOutBtn) {
  signOutBtn.addEventListener("click", function () {
    signOutUser();
  });
}

function friendlyError(err) {
  var code = err && err.code ? err.code : "";
  var map = {
    "auth/invalid-email": "That email address doesn't look right.",
    "auth/user-not-found": "No account found with that email.",
    "auth/wrong-password": "Incorrect password.",
    "auth/invalid-credential": "Incorrect email or password.",
    "auth/email-already-in-use": "An account already exists with that email — try signing in instead.",
    "auth/weak-password": "Password should be at least 6 characters."
  };
  return map[code] || (err && err.message) || "Something went wrong. Please try again.";
}

async function init() {
  if (!isBackendConfigured()) {
    authTabs.classList.add("hidden");
    signinForm.classList.add("hidden");
    signupForm.classList.add("hidden");
    authNotConfigured.classList.remove("hidden");
    return;
  }

  await onAuthChange(function (user) {
    if (user) {
      authTabs.classList.add("hidden");
      signinForm.classList.add("hidden");
      signupForm.classList.add("hidden");
      authSignedIn.classList.remove("hidden");
      signedInEmail.textContent = user.email;
      clearMessage();
    } else {
      authSignedIn.classList.add("hidden");
      var activeTab = authTabs.querySelector(".auth-tab.active");
      var isSignup = activeTab && activeTab.getAttribute("data-tab") === "signup";
      signinForm.classList.toggle("hidden", isSignup);
      signupForm.classList.toggle("hidden", !isSignup);
    }
  });
}

init();
