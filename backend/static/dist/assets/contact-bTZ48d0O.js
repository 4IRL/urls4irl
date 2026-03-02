import { $ as n, i as l } from "./navbar-shared-gG1g8UXG.js";
import "./security-check-2tLiMbrB.js";
n(document).ready(() => {
  l();
  const a = n("form#ContactForm");
  if (!a.length) return;
  a.on("submit", function () {
    const e = n(this).find('input[type="submit"]');
    e.prop("disabled", !0), e.val("Sending...");
  });
  const t = n('input[data-sent="true"]');
  if (t.length) {
    const e = t.val();
    t.prop("disabled", !0);
    let i = 5;
    t.val(`Submitted! Please wait ${i}s...`);
    const s = setInterval(() => {
      i--,
        i > 0
          ? t.val(`Submitted! Please wait ${i}s...`)
          : (clearInterval(s), t.prop("disabled", !1), t.val(e));
    }, 1e3);
  }
});
//# sourceMappingURL=contact-bTZ48d0O.js.map
