export function initChat({ threadEl, formEl, inputEl, onSubmit, onState }) {
  const payload = {
    goal: "",
    channel_id: null,
  };

  const steps = [
    {
      key: "goal",
      prompt: "What is your goal?",
      apply: (value) => {
        payload.goal = value.trim();
      },
    },
    {
      key: "content",
      prompt: "What type of content are you targeting? (for example: Shorts, Long-form, Mixed)",
      apply: (value) => {
        const part = value.trim();
        if (part) {
          payload.goal = `${payload.goal} with ${part.toLowerCase()}`;
        }
      },
    },
    {
      key: "hasChannel",
      prompt: "Do you have a channel ID? (yes/no)",
      apply: (value) => {
        payload._hasChannel = value.trim().toLowerCase().startsWith("y");
      },
    },
    {
      key: "channelId",
      prompt: "Paste your channel ID.",
      visible: () => payload._hasChannel,
      apply: (value) => {
        payload.channel_id = value.trim() || null;
      },
    },
  ];

  let stepIndex = 0;

  function scrollToBottom() {
    threadEl.scrollTop = threadEl.scrollHeight;
  }

  function pushMessage(kind, text) {
    const bubble = document.createElement("div");
    bubble.className = `bubble ${kind}`;
    bubble.textContent = text;
    threadEl.appendChild(bubble);
    scrollToBottom();
  }

  function askCurrentStep() {
    while (stepIndex < steps.length && steps[stepIndex].visible && !steps[stepIndex].visible()) {
      stepIndex += 1;
    }

    if (stepIndex >= steps.length) {
      const finalPayload = {
        goal: payload.goal,
        channel_id: payload.channel_id,
      };

      pushMessage("bot", "Great. Strategy request is ready. Generating now.");
      onState("Payload ready");
      onSubmit(finalPayload);

      stepIndex = 0;
      payload.goal = "";
      payload.channel_id = null;
      payload._hasChannel = false;
      setTimeout(() => {
        pushMessage("bot", "Want another strategy? Tell me your new goal.");
      }, 400);
      return;
    }

    const next = steps[stepIndex];
    onState("Collecting input");

    setTimeout(() => {
      pushMessage("bot", next.prompt);
      inputEl.focus();
    }, 280);
  }

  formEl.addEventListener("submit", (event) => {
    event.preventDefault();

    const value = inputEl.value.trim();
    if (!value) {
      return;
    }

    pushMessage("user", value);

    const current = steps[stepIndex];
    if (current) {
      current.apply(value);
      stepIndex += 1;
    }

    inputEl.value = "";
    askCurrentStep();
  });

  pushMessage("bot", "What is your goal?");
}
