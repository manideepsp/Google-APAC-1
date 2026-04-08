function scrollToBottom(threadEl) {
  threadEl.scrollTop = threadEl.scrollHeight;
}

function pushMessage(threadEl, kind, text) {
  const bubble = document.createElement("div");
  bubble.className = `bubble ${kind}`;
  bubble.textContent = text;
  threadEl.appendChild(bubble);
  scrollToBottom(threadEl);
}

export function initChat({ threadEl, formEl, inputEl, onState, onUserMessage, onToast }) {
  const history = [];

  async function handleUserMessage(value) {
    pushMessage(threadEl, "user", value);
    history.push({ role: "user", text: value });
    onState("Thinking");

    try {
      const result = await onUserMessage(value, history);
      const assistant = String(result?.assistant_message || "I updated your goal draft.").trim();
      const nextQuestion = String(result?.next_question || "").trim();

      pushMessage(threadEl, "bot", assistant);
      history.push({ role: "assistant", text: assistant });

      if (nextQuestion) {
        setTimeout(() => {
          pushMessage(threadEl, "bot", nextQuestion);
          history.push({ role: "assistant", text: nextQuestion });
        }, 250);
      }

      onState(result?.ready ? "Goal ready" : "Collecting input");
      if (onToast && result?.ready) {
        onToast("success", "Goal ready", "You can now generate a strategy from your parameters.");
      }
    } catch (err) {
      pushMessage(threadEl, "bot", "I hit an error while refining the goal. Please try again.");
      onState("Goal assistant error");
      if (onToast) {
        onToast("error", "Goal assistant failed", String(err?.message || err || "Unknown error"));
      }
      throw err;
    }
  }

  formEl.addEventListener("submit", async (event) => {
    event.preventDefault();

    const value = inputEl.value.trim();
    if (!value) {
      return;
    }

    inputEl.value = "";
    try {
      await handleUserMessage(value);
    } catch {
      // Error state and feedback are already handled in handleUserMessage.
    }
    inputEl.focus();
  });

  pushMessage(threadEl, "bot", "Tell me your goal. I will ask follow-up questions and keep refining parameters.");
}
