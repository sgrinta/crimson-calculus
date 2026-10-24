(function () {
  function promptEl() {
    return document.getElementById("prompt");
  }

  function sendEl() {
    return document.getElementById("send");
  }

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    const prompt = promptEl();
    if (!prompt || document.activeElement !== prompt || prompt.disabled) return;
    event.preventDefault();
    const send = sendEl();
    if (send && !send.disabled) send.click();
  });

  function scrollThread() {
    const thread = document.getElementById("thread");
    if (thread) thread.scrollTop = thread.scrollHeight;
  }

  function watchThread() {
    const thread = document.getElementById("thread");
    if (!thread || thread.dataset.observed === "1") return;
    thread.dataset.observed = "1";
    new MutationObserver(scrollThread).observe(thread, {
      childList: true,
      subtree: true,
    });
    scrollThread();
  }

  document.addEventListener("DOMContentLoaded", watchThread);
  new MutationObserver(watchThread).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
