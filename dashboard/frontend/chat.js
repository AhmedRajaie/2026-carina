// Isolated UI/state module for the dashboard assistant.
(() => {
  const api = window.location.protocol === "file:" ? "http://localhost:8000" : window.location.origin;
  const suggestions = [
    "How is my portfolio performing?",
    "Show me my current positions",
    "What is my total profit or loss?",
    "Explain my portfolio performance",
    "What does this metric mean?",
  ];
  const state = { history: [], opened: false, loading: false };
  const elements = {
    launcher: document.getElementById("chatLauncher"), panel: document.getElementById("chatPanel"),
    close: document.getElementById("chatClose"), body: document.getElementById("chatBody"),
    messages: document.getElementById("chatMessages"), suggestions: document.getElementById("chatSuggestions"),
    form: document.getElementById("chatForm"), input: document.getElementById("chatInput"), send: document.getElementById("chatSend"),
  };

  function addMessage(role, content) {
    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role}`;
    bubble.textContent = content;
    elements.messages.appendChild(bubble);
    elements.body.scrollTop = elements.body.scrollHeight;
  }

  function setLoading(loading) {
    state.loading = loading;
    elements.input.disabled = loading;
    elements.send.disabled = loading;
    const previous = document.getElementById("chatTyping");
    if (previous) previous.remove();
    if (loading) {
      const typing = document.createElement("div");
      typing.id = "chatTyping";
      typing.className = "chat-typing";
      typing.setAttribute("aria-label", "Assistant is typing");
      typing.innerHTML = "Thinking <i></i><i></i><i></i>";
      elements.messages.appendChild(typing);
      elements.body.scrollTop = elements.body.scrollHeight;
    }
  }

  function renderSuggestions() {
    elements.suggestions.replaceChildren();
    for (const text of suggestions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chat-suggestion";
      button.textContent = text;
      button.addEventListener("click", () => send(text));
      elements.suggestions.appendChild(button);
    }
  }

  function open() {
    state.opened = true;
    elements.panel.hidden = false;
    elements.launcher.setAttribute("aria-expanded", "true");
    if (!elements.messages.childElementCount) {
      addMessage("assistant", "Hi — I can explain the live strategy metrics, fixed-dollar account balance, open positions, scanner signals, and backtest activity.");
      renderSuggestions();
    }
    elements.input.focus();
  }

  function close() {
    state.opened = false;
    elements.panel.hidden = true;
    elements.launcher.setAttribute("aria-expanded", "false");
    elements.launcher.focus();
  }

  async function send(rawMessage) {
    const message = rawMessage.trim();
    if (!message || state.loading) return;
    elements.input.value = "";
    elements.suggestions.replaceChildren();
    addMessage("user", message);
    setLoading(true);
    const scope = document.getElementById("universeSelect")?.value || "core";
    try {
      const response = await fetch(`${api}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, scope, history: state.history.slice(-8) }),
      });
      if (!response.ok) throw new Error("The assistant is temporarily unavailable.");
      const result = await response.json();
      addMessage("assistant", result.reply);
      state.history.push({ role: "user", content: message }, { role: "assistant", content: result.reply });
    } catch (error) {
      addMessage("assistant", "I couldn't retrieve the dashboard data just now. Please try again in a moment.");
    } finally {
      setLoading(false);
      elements.input.focus();
    }
  }

  elements.launcher.addEventListener("click", () => state.opened ? close() : open());
  elements.close.addEventListener("click", close);
  elements.form.addEventListener("submit", (event) => { event.preventDefault(); send(elements.input.value); });
})();
