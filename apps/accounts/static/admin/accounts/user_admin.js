(function ($) {
  function pad(value) {
    return String(value).padStart(2, "0");
  }

  function applyNowToSplitWidget() {
    const dateInput = document.getElementById("id_email_verified_at_0");
    const timeInput = document.getElementById("id_email_verified_at_1");
    if (!dateInput || !timeInput) {
      return false;
    }

    const now = new Date();
    dateInput.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    timeInput.value = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    dateInput.dispatchEvent(new Event("change", { bubbles: true }));
    timeInput.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }

  function applyNowToSingleWidget() {
    const input = document.getElementById("id_email_verified_at");
    if (!input) {
      return;
    }

    const now = new Date();
    input.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function attachNowButton() {
    const dateInput = document.getElementById("id_email_verified_at_0");
    const timeInput = document.getElementById("id_email_verified_at_1");
    const singleInput = document.getElementById("id_email_verified_at");

    const anchor = timeInput || singleInput || dateInput;
    if (!anchor || document.getElementById("email-verified-at-now-btn")) {
      return;
    }

    const btn = document.createElement("button");
    btn.type = "button";
    btn.id = "email-verified-at-now-btn";
    btn.className = "button";
    btn.style.marginLeft = "8px";
    btn.textContent = "Now";
    btn.addEventListener("click", function () {
      if (!applyNowToSplitWidget()) {
        applyNowToSingleWidget();
      }
    });

    anchor.insertAdjacentElement("afterend", btn);
  }

  $(function () {
    attachNowButton();
  });
})(django.jQuery);
