(() => {
  "use strict";

  const WA = "34648031210";
  const MAIL = "mail@rentabikebcn.com";
  const $ = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => Array.from(c.querySelectorAll(s));
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const root = document.documentElement;

  /* ---------------- i18n ---------------- */
  const dict = window.I18N || { enJs: {}, es: {}, ru: {} };
  const EN = { ...dict.enJs };
  EN["meta.title"] = document.title;
  EN["meta.desc"] = $('meta[name="description"]')?.content || "";
  let lang = "en";

  // Capture the English source text straight from the markup.
  $$("[data-i18n]").forEach((el) => {
    const k = el.dataset.i18n;
    const html = el.hasAttribute("data-i18n-html");
    if (!(k in EN)) EN[k] = html ? el.innerHTML : el.textContent;
  });
  $$("[data-i18n-attr]").forEach((el) => {
    el.dataset.i18nAttr.split(";").forEach((pair) => {
      const [attr, key] = pair.split(":");
      if (!(key in EN)) EN[key] = el.getAttribute(attr) || "";
    });
  });

  const t = (key, vars) => {
    let s = (lang !== "en" && dict[lang]?.[key]) || EN[key] || key;
    if (vars) s = s.replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? "");
    return s;
  };

  function applyLang(next) {
    lang = next;
    root.lang = next;
    $$("[data-i18n]").forEach((el) => {
      const k = el.dataset.i18n;
      if (el.hasAttribute("data-i18n-html")) el.innerHTML = t(k);
      else el.textContent = t(k);
    });
    $$("[data-i18n-attr]").forEach((el) => {
      el.dataset.i18nAttr.split(";").forEach((pair) => {
        const [attr, key] = pair.split(":");
        el.setAttribute(attr, t(key));
      });
    });
    document.title = t("meta.title");
    $('meta[name="description"]')?.setAttribute("content", t("meta.desc"));
    $$("[data-lang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === next)));
    refreshLinks();
    try { localStorage.setItem("rab-lang", next); } catch (_) { /* private mode */ }
  }

  /* ---------------- WhatsApp links ---------------- */
  const waUrl = (msg) => `https://wa.me/${WA}?text=${encodeURIComponent(msg)}`;

  function bikeLink(card) {
    const pressed = $('.durations [aria-pressed="true"]', card);
    const price = $(".amount", card).textContent;
    const msg = t("wa.bike", {
      bike: t(card.dataset.name),
      dur: t(pressed.dataset.l).toLowerCase(),
      price,
    });
    $("[data-wa-bike]", card).href = waUrl(msg);
  }

  function refreshLinks() {
    $$("[data-wa]").forEach((a) => (a.href = waUrl(t(a.dataset.waMsg || "wa.general"))));
    $$(".bike-card").forEach(bikeLink);
    $$(".tour-card").forEach((card) => {
      $("[data-wa-tour]", card).href = waUrl(t("wa.tour", { tour: t(card.dataset.tour) }));
    });
  }

  /* ---------------- Price selectors ---------------- */
  $$(".bike-card").forEach((card) => {
    const amount = $(".amount", card);
    $$(".durations button", card).forEach((btn) => {
      btn.addEventListener("click", () => {
        $$(".durations button", card).forEach((b) => b.setAttribute("aria-pressed", "false"));
        btn.setAttribute("aria-pressed", "true");
        amount.textContent = `€${btn.dataset.p}`;
        amount.removeAttribute("data-pop");
        void amount.offsetWidth;
        amount.setAttribute("data-pop", "");
        bikeLink(card);
      });
    });
  });

  /* ---------------- Mobile drawer ---------------- */
  const burger = $(".burger");
  const drawer = $("#drawer");
  drawer.inert = true;

  function setMenu(open) {
    document.body.classList.toggle("menu-open", open);
    document.body.classList.toggle("no-scroll", open);
    burger.setAttribute("aria-expanded", String(open));
    drawer.setAttribute("aria-hidden", String(!open));
    drawer.inert = !open;
    if (open) drawer.querySelector("a")?.focus({ preventScroll: true });
    else burger.focus({ preventScroll: true });
  }
  burger.addEventListener("click", () => setMenu(true));
  $$("[data-close-menu]").forEach((el) => el.addEventListener("click", () => setMenu(false)));
  $$("#drawer nav a, #drawer .btn").forEach((a) => a.addEventListener("click", () => document.body.classList.contains("menu-open") && setMenu(false)));
  addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.body.classList.contains("menu-open")) setMenu(false);
  });
  matchMedia("(min-width: 960px)").addEventListener("change", (m) => m.matches && document.body.classList.contains("menu-open") && setMenu(false));

  /* ---------------- Header, sticky CTA, parallax ---------------- */
  const header = $(".site-header");
  const sticky = $("#sticky-cta");
  const hero = $(".hero");
  const parallax = $$("[data-parallax]");
  const heroImg = $("[data-parallax-img]");
  let ticking = false;

  function onScroll() {
    const y = scrollY;
    header.classList.toggle("is-scrolled", y > 12);
    if (!reduceMotion && y < hero.offsetHeight * 1.2) {
      parallax.forEach((el) => (el.style.transform = `translate3d(0, ${(y * parseFloat(el.dataset.parallax)).toFixed(1)}px, 0)`));
      if (heroImg) heroImg.style.transform = `translate3d(0, ${-Math.min(y * 0.04, 12).toFixed(1)}px, 0)`;
    }
    ticking = false;
  }
  addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
  onScroll();

  // Sticky CTA appears after the hero and hides near booking sections.
  if ("IntersectionObserver" in window) {
    let pastHero = false;
    const hidden = new Set();
    const sync = () => sticky.classList.toggle("is-on", pastHero && hidden.size === 0);
    new IntersectionObserver(([e]) => { pastHero = !e.isIntersecting && e.boundingClientRect.top < 0; sync(); }, { threshold: 0 }).observe(hero);
    const hideObs = new IntersectionObserver((entries) => {
      entries.forEach((e) => (e.isIntersecting ? hidden.add(e.target) : hidden.delete(e.target)));
      sync();
    }, { threshold: 0.15 });
    ["#book", ".final-cta", ".site-footer"].forEach((s) => { const el = $(s); if (el) hideObs.observe(el); });
  }

  /* ---------------- Scroll reveal ---------------- */
  const revealEls = $$(".reveal");
  if ("IntersectionObserver" in window && !reduceMotion) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("is-in"); io.unobserve(e.target); } });
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
    revealEls.forEach((el) => io.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("is-in"));
  }

  /* ---------------- Active nav link ---------------- */
  if ("IntersectionObserver" in window) {
    const links = $$(".nav-links a");
    const map = new Map(links.map((a) => [a.getAttribute("href").slice(1), a]));
    const spy = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { links.forEach((l) => l.classList.remove("is-active")); map.get(e.target.id)?.classList.add("is-active"); }
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    map.forEach((_, id) => { const s = document.getElementById(id); if (s) spy.observe(s); });
  }

  /* ---------------- Booking form ---------------- */
  const form = $("#book-form");
  const dateInput = $("#f-date");
  const iso = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  dateInput.min = iso(new Date());
  dateInput.value = iso(new Date(Date.now() + 864e5));

  function bookingMessage() {
    const f = new FormData(form);
    return t("wa.form", {
      what: t(f.get("bike")),
      name: String(f.get("name")).trim(),
      date: f.get("date"),
      time: f.get("time"),
      dur: t(f.get("dur")),
      n: f.get("n"),
      shop: t(f.get("shop") + ".opt"),
    });
  }
  function validate() {
    let ok = true;
    ["f-name", "f-date"].forEach((id) => {
      const el = document.getElementById(id);
      const bad = !el.value.trim();
      el.setAttribute("aria-invalid", String(bad));
      if (bad && ok) el.focus();
      ok = ok && !bad;
    });
    return ok;
  }
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (!validate()) return;
    window.open(waUrl(bookingMessage()), "_blank", "noopener");
  });
  $("[data-mail]").addEventListener("click", (e) => {
    e.preventDefault();
    if (!validate()) return;
    location.href = `mailto:${MAIL}?subject=${encodeURIComponent(t("mail.subject"))}&body=${encodeURIComponent(bookingMessage())}`;
  });

  /* ---------------- Map tabs ---------------- */
  const map = $("#map");
  const dir = $("[data-directions]");
  $$(".shop").forEach((tab) => {
    tab.addEventListener("click", () => {
      $$(".shop").forEach((s) => s.setAttribute("aria-selected", String(s === tab)));
      map.src = `https://maps.google.com/maps?q=${tab.dataset.map}&z=16&output=embed`;
      dir.href = `https://www.google.com/maps/dir/?api=1&destination=${tab.dataset.dir}`;
    });
  });

  /* ---------------- Lightbox ---------------- */
  const box = $("#lightbox");
  const boxImg = $("#lightbox-img");
  const boxCap = $("#lightbox-cap");
  $$(".g-item").forEach((item) => {
    item.addEventListener("click", () => {
      boxImg.src = item.dataset.full;
      boxCap.textContent = t(item.dataset.cap);
      boxImg.alt = boxCap.textContent;
      box.showModal();
    });
  });
  $("#lightbox-close").addEventListener("click", () => box.close());
  box.addEventListener("click", (e) => { if (e.target === box) box.close(); });

  /* ---------------- Language switch ---------------- */
  $$("[data-lang]").forEach((b) => b.addEventListener("click", () => applyLang(b.dataset.lang)));
  let saved = null;
  try { saved = localStorage.getItem("rab-lang"); } catch (_) { /* ignore */ }
  const guess = (navigator.language || "en").slice(0, 2);
  const initial = ["en", "es", "ru"].includes(saved) ? saved : ["es", "ru"].includes(guess) ? guess : "en";

  $$("[data-year]").forEach((el) => (el.textContent = new Date().getFullYear()));
  refreshLinks();
  if (initial !== "en") applyLang(initial);
})();
