function setMessage(text, type = "") {
  const el = document.getElementById("message");
  if (!el) return;
  el.textContent = text;
  el.className = `message ${type}`.trim();
}

async function postJson(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || data.message || `Request failed: ${res.status}`);
  }

  return data;
}

function setSessionFromResponse(data) {
  localStorage.setItem("session_token", data.session_token);
  localStorage.setItem("user_email", data.user?.email || "");
  window.location.href = "/";
}

const loginForm = document.getElementById("loginForm");
if (loginForm) {
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    try {
      setMessage("Signing in...");
      const data = await postJson("/auth/login", { email, password });
      setSessionFromResponse(data);
    } catch (err) {
      setMessage(err.message, "error");
    }
  });
}

const registerForm = document.getElementById("registerForm");
if (registerForm) {
  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;
    const confirm = document.getElementById("confirmPassword").value;

    if (password !== confirm) {
      setMessage("Passwords do not match", "error");
      return;
    }

    try {
      setMessage("Creating account...");
      const data = await postJson("/auth/register", { email, password });
      setSessionFromResponse(data);
    } catch (err) {
      setMessage(err.message, "error");
    }
  });
}

const forgotForm = document.getElementById("forgotForm");
if (forgotForm) {
  forgotForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value;

    try {
      const data = await postJson("/auth/forgot-password", { email });
      setMessage(data.message, "success");

      const tokenBox = document.getElementById("resetTokenBox");
      if (tokenBox) {
        tokenBox.textContent = data.reset_token || "No token generated for this email.";
      }
    } catch (err) {
      setMessage(err.message, "error");
    }
  });
}

const resetForm = document.getElementById("resetForm");
if (resetForm) {
  resetForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const resetToken = document.getElementById("resetToken").value;
    const newPassword = document.getElementById("newPassword").value;

    try {
      const data = await postJson("/auth/reset-password", {
        reset_token: resetToken,
        new_password: newPassword,
      });
      setMessage(data.message, "success");
    } catch (err) {
      setMessage(err.message, "error");
    }
  });
}
