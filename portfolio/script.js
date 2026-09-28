(() => {
  "use strict";

  const EMAIL = "rohitpujari7114@gmail.com";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const rnd = (a) => (Math.random() * 2 - 1) * a;
  const pad = (n) => String(n).padStart(2, "0");
  const store = {
    get(k) { try { return sessionStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { sessionStorage.setItem(k, v); } catch { /* storage blocked */ } },
  };
  const onVisible = (el, cb, threshold = 0.15) => {
    const io = new IntersectionObserver((es) => es.forEach((e) => cb(e.isIntersecting)), { threshold });
    io.observe(el);
  };
  // A timer that only advances while `isLive()` is true, so paused sections resume where they stopped.
  const pausableWait = (ms, isLive) => new Promise((res) => {
    let left = ms, last = performance.now();
    const tick = (now) => {
      if (isLive() && !document.hidden) left -= now - last;
      last = now;
      left <= 0 ? res() : requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  $("#year").textContent = new Date().getFullYear();
  const root = document.documentElement;

  /* ---------- Boot sequence ---------- */
  const bootDone = new Promise((resolve) => {
    const el = $("#boot");
    if (reduceMotion || store.get("ro-booted")) return resolve();
    store.set("ro-booted", "1");
    el.hidden = false;
    const log = $("#bootLog");
    const lines = [
      '<span class="dim">[    0.000000]</span> ro-cloud kernel: Linux 6.8.0-1012-aws x86_64',
      '<span class="ok">[  OK  ]</span> Reached target Network · eth0 10.0.2.14/24',
      '<span class="ok">[  OK  ]</span> Mounted EBS volume /dev/nvme1n1 → /var/lib/data',
      '<span class="ok">[  OK  ]</span> Associated Elastic IP 44.210.213.12',
      '<span class="ok">[  OK  ]</span> Started containerd.service',
      '<span class="ok">[  OK  ]</span> Started kubelet.service · 3/3 pods Running',
      '<span class="ok">[  OK  ]</span> OpsMind guardrails armed (2/2)',
      '',
      '<span class="hi">ro@cloud:~$ ./portfolio --serve --zero-downtime</span>',
    ];
    let i = 0, done = false;
    const finish = () => {
      if (done) return;
      done = true;
      el.classList.add("is-done");
      window.removeEventListener("keydown", finish);
      setTimeout(() => { el.hidden = true; }, 600);
      resolve();
    };
    window.addEventListener("keydown", finish);
    el.addEventListener("click", finish);
    const step = () => {
      if (done) return;
      if (i >= lines.length) return setTimeout(finish, 420);
      log.innerHTML += lines[i++] + "\n";
      setTimeout(step, 70 + Math.random() * 70);
    };
    step();
  });

  // Hero intro plays once the boot overlay lifts.
  if (!reduceMotion) {
    root.classList.add("intro");
    bootDone.then(() => requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove("intro"))));
  }

  /* ---------- Scroll: nav state, progress bar, parallax, pinned sections ---------- */
  const nav = $("#nav");
  const toggle = $("#navToggle");
  const links = $("#navLinks");
  const progress = $(".scroll-progress");
  const scrollFns = [];
  const parallaxEls = reduceMotion ? [] : $$("[data-parallax]");

  scrollFns.push((y) => {
    nav.classList.toggle("is-scrolled", y > 20);
    const max = root.scrollHeight - window.innerHeight;
    progress.style.transform = `scaleX(${max > 0 ? y / max : 0})`;
    parallaxEls.forEach((el) => { el.style.transform = `translate3d(0, ${y * parseFloat(el.dataset.parallax)}px, 0)`; });
  });
  let ticking = false;
  const runScroll = () => { const y = window.scrollY; scrollFns.forEach((f) => f(y)); ticking = false; };
  window.addEventListener("scroll", () => {
    if (!ticking) { requestAnimationFrame(runScroll); ticking = true; }
  }, { passive: true });
  window.addEventListener("resize", () => requestAnimationFrame(runScroll));

  const setMenu = (open) => {
    toggle.setAttribute("aria-expanded", String(open));
    links.classList.toggle("is-open", open);
    nav.classList.toggle("menu-open", open);
  };
  toggle.addEventListener("click", () => setMenu(toggle.getAttribute("aria-expanded") !== "true"));
  $$("a", links).forEach((a) => a.addEventListener("click", () => setMenu(false)));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setMenu(false); });

  /* ---------- Active nav link ---------- */
  const navLinks = $$(".nav__link");
  const sectionObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      navLinks.forEach((l) => l.classList.toggle("is-active", l.getAttribute("href") === `#${entry.target.id}`));
    });
  }, { rootMargin: "-45% 0px -50% 0px" });
  $$("main > section[id]").forEach((s) => sectionObserver.observe(s));

  /* ---------- Reveal on scroll ----------
     Everything is visible at rest; only elements that start below the fold
     are hidden, then faded in (with a small sibling stagger) as they enter. */
  const fold = window.innerHeight * 0.92;
  const belowFold = (el) => el.getBoundingClientRect().top > fold;
  const revealEls = $$(".reveal");
  revealEls.forEach((el) => {
    const siblings = [...el.parentElement.children].filter((c) => c.classList.contains("reveal"));
    el.style.setProperty("--d", `${Math.min(siblings.indexOf(el), 5) * 0.08}s`);
    if (!reduceMotion && belowFold(el)) el.classList.add("is-pending");
  });

  // Section titles: split into words that rise out of a mask.
  const splitWords = (el) => {
    let wi = 0;
    const walk = (node) => {
      [...node.childNodes].forEach((n) => {
        if (n.nodeType === 1) return walk(n);
        if (n.nodeType !== 3) return;
        const frag = document.createDocumentFragment();
        n.textContent.split(/(\s+)/).forEach((part) => {
          if (!part) return;
          if (/^\s+$/.test(part)) return frag.appendChild(document.createTextNode(part));
          const w = document.createElement("span");
          w.className = "w";
          const inner = document.createElement("span");
          inner.textContent = part;
          inner.style.setProperty("--wi", wi++);
          w.appendChild(inner);
          frag.appendChild(w);
        });
        n.replaceWith(frag);
      });
    };
    walk(el);
  };
  const splitEls = reduceMotion ? [] : $$(".split");
  splitEls.forEach((el) => {
    splitWords(el);
    if (belowFold(el)) el.classList.add("is-hidden");
  });

  const revealObserver = new IntersectionObserver((entries, obs) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.remove("is-pending", "is-hidden");
      obs.unobserve(entry.target);
    });
  }, { threshold: 0.1, rootMargin: "0px 0px -40px 0px" });
  revealEls.filter((el) => el.classList.contains("is-pending")).forEach((el) => revealObserver.observe(el));
  splitEls.filter((el) => el.classList.contains("is-hidden")).forEach((el) => revealObserver.observe(el));

  /* ---------- Stat counters ---------- */
  const uptimeEl = $("#uptime");
  uptimeEl.dataset.count = "99.99";
  uptimeEl.dataset.decimals = "2";
  const animateCount = (el) => {
    const target = parseFloat(el.dataset.count);
    const decimals = parseInt(el.dataset.decimals || "0", 10);
    if (reduceMotion) { el.textContent = target.toFixed(decimals); return; }
    const duration = 1800;
    const start = performance.now();
    const step = (now) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 4);
      el.textContent = (target * eased).toFixed(decimals);
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  const countObserver = new IntersectionObserver((entries, obs) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      bootDone.then(() => animateCount(entry.target));
      obs.unobserve(entry.target);
    });
  }, { threshold: 0.6 });
  $$("[data-count]").forEach((el) => countObserver.observe(el));

  /* ---------- Typed role ---------- */
  const typed = $("#typed");
  const roles = [
    "Cloud & DevOps Engineer | SRE Specialist",
    "AWS · Docker · Kubernetes",
    "Building self-healing systems",
    "CI/CD & Infrastructure as Code",
  ];
  if (!reduceMotion) {
    let r = 0, i = roles[0].length, deleting = true;
    const tick = () => {
      const word = roles[r];
      typed.textContent = word.slice(0, i);
      if (deleting) {
        i--;
        if (i < 0) { deleting = false; r = (r + 1) % roles.length; i = 0; return setTimeout(tick, 300); }
        return setTimeout(tick, 28);
      }
      i++;
      if (i > roles[r].length) { deleting = true; i = roles[r].length; return setTimeout(tick, 2400); }
      setTimeout(tick, 55);
    };
    setTimeout(tick, 3200);
  }

  /* ---------- Custom cursor, magnetic buttons, card glow ---------- */
  if (finePointer && !reduceMotion) {
    root.classList.add("has-cursor");
    const cur = $(".cursor"), dot = $(".cursor__dot"), ring = $(".cursor__ring");
    let mx = -100, my = -100, rx = -100, ry = -100;
    window.addEventListener("pointermove", (e) => {
      mx = e.clientX; my = e.clientY;
      cur.classList.remove("is-hidden");
      dot.style.transform = `translate3d(${mx}px, ${my}px, 0)`;
    }, { passive: true });
    root.addEventListener("pointerleave", () => cur.classList.add("is-hidden"));
    window.addEventListener("pointerdown", () => cur.classList.add("is-down"));
    window.addEventListener("pointerup", () => cur.classList.remove("is-down"));
    document.addEventListener("pointerover", (e) => {
      cur.classList.toggle("is-hover", !!e.target.closest("a, button, [data-magnetic], .palette__item, .tags li"));
    });
    const follow = () => {
      rx += (mx - rx) * 0.2; ry += (my - ry) * 0.2;
      ring.style.transform = `translate3d(${rx}px, ${ry}px, 0)`;
      requestAnimationFrame(follow);
    };
    follow();

    $$("[data-magnetic]").forEach((el) => {
      const k = el.classList.contains("social") ? 0.4 : 0.28;
      el.addEventListener("pointermove", (e) => {
        const r = el.getBoundingClientRect();
        const x = e.clientX - (r.left + r.width / 2), y = e.clientY - (r.top + r.height / 2);
        el.style.transform = `translate(${x * k}px, ${y * k * 1.2}px)`;
      });
      el.addEventListener("pointerleave", () => { el.style.transform = ""; });
    });

    $$(".glow").forEach((el) => el.addEventListener("pointermove", (e) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${e.clientX - r.left}px`);
      el.style.setProperty("--my", `${e.clientY - r.top}px`);
    }, { passive: true }));
  }

  /* ---------- Hero: live AWS console ---------- */
  (() => {
    const box = $("#console");
    let live = true;
    onVisible(box, (v) => { live = v; }, 0);
    const sparks = $$(".spark", box).map((el) => {
      const base = +el.dataset.base;
      const pts = [];
      let v = base;
      for (let i = 0; i < 40; i++) { v = clamp(v + rnd(6) + (base - v) * 0.2, 4, 96); pts.push(v); }
      return { base, pts, val: $("b", el), line: $(".spark__line", el), area: $(".spark__area", el) };
    });
    const draw = (s) => {
      const n = s.pts.length;
      const d = s.pts.map((v, i) => `${(i / (n - 1) * 120).toFixed(1)},${(30 - v / 100 * 30).toFixed(1)}`);
      s.line.setAttribute("d", "M" + d.join("L"));
      s.area.setAttribute("d", "M0,30L" + d.join("L") + "L120,30Z");
      s.val.textContent = `${Math.round(s.pts[n - 1])}%`;
    };
    sparks.forEach(draw);

    const ups = $$("[data-up]", box);
    const t0 = Date.now();
    const fmtUp = (s) => `${Math.floor(s / 86400)}d ${pad(Math.floor(s / 3600) % 24)}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`;
    const tickUp = () => ups.forEach((el) => { el.textContent = fmtUp(+el.dataset.up + Math.floor((Date.now() - t0) / 1000)); });
    tickUp();
    const hc = $("#hcAgo");
    let hcN = 1;
    if (reduceMotion) return;
    setInterval(() => {
      tickUp();
      hcN = hcN >= 9 ? 0 : hcN + 1;
      hc.textContent = `${hcN}s`;
      if (!live || document.hidden) return;
      sparks.forEach((s) => {
        const last = s.pts[s.pts.length - 1];
        let v = last + rnd(7) + (s.base - last) * 0.18;
        if (Math.random() < 0.06) v += 16;
        s.pts.push(clamp(v, 4, 96));
        s.pts.shift();
        draw(s);
      });
    }, 1000);
  })();

  /* ---------- Systems: isometric AWS architecture + self-healing loop ---------- */
  const TERM_SCRIPT = [
    { cls: "t-prompt", text: "ro@opsmind:~$ ", cmd: "kubectl get pods -n prod" },
    { cls: "t-dim", text: "NAME                      READY   STATUS" },
    { cls: "t-err", text: "api-gateway-7f9c4-x2kq    0/1     OOMKilled (137)" },
    { cls: "t-warn", text: "[chaos] memory saturation detected · 2GB ceiling enforced" },
    { cls: "t-info", text: "[aiops] groq/llama-3 → diagnosing root cause..." },
    { cls: "t-info", text: "[guardrail 1/2] schema validation ........ PASS" },
    { cls: "t-info", text: "[guardrail 2/2] resource policy check .... PASS" },
    { cls: "t-ok", text: "[remediate] patched limits · rolling restart" },
    { cls: "t-dim", text: "api-gateway-7f9c4-p8zn    1/1     Running" },
    { cls: "t-ok", text: "✔ recovered in 25.5s · uptime 99.99% · zero downtime" },
  ];

  (() => {
    const svg = $("#isoSvg");
    const term = $("#terminal");
    const NS = "http://www.w3.org/2000/svg";
    const U = 20, C = U * 0.866, S = U * 0.5, Z = U * 0.9;
    const P = (x, y, z = 0) => [(x - y) * C, (x + y) * S - z * Z];
    const mk = (tag, attrs, parent) => {
      const e = document.createElementNS(NS, tag);
      Object.entries(attrs || {}).forEach(([k, v]) => e.setAttribute(k, v));
      if (parent) parent.appendChild(e);
      return e;
    };
    const pts = (arr) => arr.map((p) => P(...p).map((n) => n.toFixed(1)).join(",")).join(" ");
    const box = (x, y, z, w, d, h, cls, parent) => {
      const g = mk("g", { class: cls || "" }, parent);
      mk("polygon", { class: "f-l", points: pts([[x, y + d, z], [x + w, y + d, z], [x + w, y + d, z + h], [x, y + d, z + h]]) }, g);
      mk("polygon", { class: "f-r", points: pts([[x + w, y, z], [x + w, y + d, z], [x + w, y + d, z + h], [x + w, y, z + h]]) }, g);
      mk("polygon", { class: "f-t", points: pts([[x, y, z + h], [x + w, y, z + h], [x + w, y + d, z + h], [x, y + d, z + h]]) }, g);
      return g;
    };
    // Text printed on the floor, running along the x axis or up the -y axis.
    const floorText = (str, x, y, z, cls, parent, axis = "x") => {
      const [sx, sy] = P(x, y, z);
      const m = axis === "x" ? [C / U, S / U, -C / U, S / U] : [C / U, -S / U, C / U, S / U];
      const t = mk("text", { class: cls, transform: `matrix(${m.map((n) => n.toFixed(4)).join(" ")} ${sx.toFixed(1)} ${sy.toFixed(1)})` }, parent);
      t.textContent = str;
      return t;
    };

    const gFloor = mk("g", {}, svg);
    const gBoxes = mk("g", {}, svg);
    const gEdges = mk("g", {}, svg);
    const gPods = mk("g", {}, svg);
    const gPk = mk("g", {}, svg);
    const gLabels = mk("g", {}, svg);

    box(0, 0, 0, 24, 17, 0.35, "slab", gFloor);
    box(1, 1, 0.35, 8, 15, 0.15, "plate", gFloor);
    box(10, 1, 0.35, 13, 15, 0.15, "plate", gFloor);
    floorText("VPC · 10.0.0.0/16 · us-east-1", 0.6, 17.9, 0, "lbl-floor", gLabels);
    floorText("public subnet · 10.0.1.0/24", 8.85, 15.6, 0.5, "lbl-floor", gLabels, "y");
    floorText("private subnet · 10.0.2.0/24", 22.85, 15.6, 0.5, "lbl-floor", gLabels, "y");

    const nodes = [
      [-6.6, 6.2, 0, 2.2, 2.2, 1.3, "", "Users", 9.25],
      [-2.8, 6.4, 0, 1.8, 1.8, 0.9, "", "DNS", 9.05],
      [3.5, 6, 0.5, 3, 3, 1.6, "", "Nginx ingress", 9.85],
      [12, 3, 0.5, 7, 6.5, 1.3, "", "EC2 · t3.medium", 10.35],
      [20.4, 3.2, 0.5, 1.9, 2, 1.1, "", "EBS", 6.05],
      [20.4, 7.6, 0.5, 1.9, 2, 1.4, "", "S3", 10.45],
      [12, 12, 0.5, 3.2, 2.4, 0.9, "", "CloudWatch", 15.25],
      [16.6, 12, 0.5, 3.4, 2.4, 1.3, "key", "OpsMind · Llama-3", 15.25],
    ];
    const boxEls = nodes.map(([x, y, z, w, d, h, cls, label, ly]) => {
      const g = box(x, y, z, w, d, h, cls, gBoxes);
      floorText(label, x, ly, z, "lbl-box", gLabels);
      return g;
    });
    const ops = boxEls[7];
    floorText("k8s node · pods", 12.4, 9.1, 1.8, "lbl-sub", gLabels);

    const edge = (points, cls = "") => mk("path", { class: `edge ${cls}`, d: "M" + points.map((p) => P(...p).map((n) => n.toFixed(1)).join(",")).join("L") }, gEdges);
    const E = {
      users: edge([[-4.4, 7.3, 0.6], [-2.8, 7.3, 0.45]]),
      dns: edge([[-1.0, 7.3, 0.45], [3.5, 7.5, 1.0]]),
      ingress: edge([[6.5, 7.5, 1.0], [12, 7.5, 1.0]]),
      ebs: edge([[19, 4.2, 1.0], [20.4, 4.2, 1.0]]),
      s3: edge([[19, 8.4, 1.0], [20.4, 8.4, 1.0]]),
      metrics: edge([[13.6, 9.5, 1.0], [13.6, 12, 1.0]], "edge--loop"),
      alert: edge([[15.2, 13.2, 0.9], [16.6, 13.2, 0.9]], "edge--loop"),
      fix: edge([[18.3, 12, 1.5], [18.3, 9.5, 1.8], [16, 5, 1.8]], "edge--loop"),
    };
    Object.values(E).forEach((p) => { p.len = p.getTotalLength(); });

    // Pods: six slots on top of the EC2 node, back row first for painter order.
    const SLOTS = [[12.6, 3.7], [14.7, 3.7], [16.8, 3.7], [12.6, 6.2], [14.7, 6.2], [16.8, 6.2]];
    const slotG = SLOTS.map(() => mk("g", {}, gPods));
    const pods = {};
    const podClass = (state) => (state === "ok" ? "pod" : `pod pod--${state}`);
    const addPod = (slot, state = "pending", animate = true) => {
      const [x, y] = SLOTS[slot];
      const g = box(x, y, 1.8, 1.3, 1.3, 1.2, podClass(state) + (animate ? " pod--enter" : ""), slotG[slot]);
      pods[slot] = g;
      if (animate) requestAnimationFrame(() => requestAnimationFrame(() => g.classList.remove("pod--enter")));
    };
    const setPod = (slot, state) => { if (pods[slot]) pods[slot].setAttribute("class", podClass(state)); };
    const removePod = (slot) => {
      const g = pods[slot];
      if (!g) return;
      delete pods[slot];
      g.classList.add("pod--enter");
      setTimeout(() => g.remove(), 600);
    };

    // Floating tags (OOMKilled on the pod, status above OpsMind).
    const makeTag = (x, y, z, tone) => {
      const [sx, sy] = P(x, y, z);
      const g = mk("g", { class: `tag tag--${tone}`, opacity: 0 }, gLabels);
      const r = mk("rect", { rx: 4, height: 18, y: sy - 32 }, g);
      const t = mk("text", { y: sy - 20, "text-anchor": "middle", x: sx }, g);
      return {
        set(text) {
          t.textContent = text;
          const w = text.length * 6.2 + 14;
          r.setAttribute("width", w); r.setAttribute("x", sx - w / 2);
        },
        show(on) { g.setAttribute("opacity", on ? 1 : 0); },
      };
    };
    const oomTag = makeTag(15.35, 4.35, 3.0, "err");
    oomTag.set("OOMKilled · exit 137");
    const opsTag = makeTag(21, 13.8, 1.8, "ops");

    // Packets travelling along one or more edges.
    const packets = [];
    const spawn = (route, cls = "", speed = 110, onDone) => {
      const g = mk("g", {}, gPk);
      mk("circle", { r: 2.4, class: `pk ${cls}` }, g);
      mk("circle", { r: 6, class: "pk-halo" }, g);
      packets.push({ g, route, i: 0, d: 0, speed, onDone });
    };
    const stepPackets = (dt) => {
      for (let n = packets.length - 1; n >= 0; n--) {
        const p = packets[n];
        p.d += p.speed * dt;
        while (p.i < p.route.length && p.d > p.route[p.i].len) { p.d -= p.route[p.i].len; p.i++; }
        if (p.i >= p.route.length) {
          p.g.remove(); packets.splice(n, 1);
          if (p.onDone) p.onDone();
          continue;
        }
        const pt = p.route[p.i].getPointAtLength(p.d);
        p.g.setAttribute("transform", `translate(${pt.x.toFixed(1)} ${pt.y.toFixed(1)})`);
      }
    };
    const requestRoute = () => {
      const r = Math.random();
      return r < 0.3 ? [E.users, E.dns, E.ingress, E.ebs] : r < 0.55 ? [E.users, E.dns, E.ingress, E.s3] : [E.users, E.dns, E.ingress];
    };

    // HUD, loop steps, timer, terminal.
    const hudReplicas = $("#isoReplicas"), hudEvent = $("#isoEvent");
    const setReplicas = (a, b) => { hudReplicas.textContent = `replicas ${a}/${b}`; };
    const setEvent = (text, tone = "") => { hudEvent.textContent = text; hudEvent.dataset.tone = tone; };
    const steps = $$("#loopSteps [data-step]");
    const setStep = (i, s) => { steps[i].className = s ? `is-${s}` : ""; };
    const timerEl = $("#loopTimer");
    const setTimer = (s) => { timerEl.textContent = `${s.toFixed(1).padStart(4, "0")}s`; };
    const esc = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    const termLine = (cls, text) => {
      const s = document.createElement("span");
      s.className = `ln ${cls}`;
      s.textContent = text;
      term.appendChild(s);
      term.scrollTop = term.scrollHeight;
    };
    const scriptLine = (i) => termLine(TERM_SCRIPT[i].cls, TERM_SCRIPT[i].text);
    const typeCmd = () => {
      const row = document.createElement("span");
      row.className = "ln";
      row.innerHTML = `<span class="t-prompt">${esc(TERM_SCRIPT[0].text)}</span><span class="t-cmd"></span>`;
      term.appendChild(row);
      const cmdEl = row.lastChild, cmd = TERM_SCRIPT[0].cmd;
      let i = 0;
      const tick = () => { cmdEl.textContent = cmd.slice(0, ++i); if (i < cmd.length) setTimeout(tick, 18); };
      tick();
      term.scrollTop = term.scrollHeight;
    };

    const baseline = () => {
      [3, 4, 5].forEach((s) => { if (pods[s]) { pods[s].remove(); delete pods[s]; } });
      [0, 1, 2].forEach((s) => (pods[s] ? setPod(s, "ok") : addPod(s, "ok", false)));
      ops.classList.remove("thinking");
      oomTag.show(false); opsTag.show(false);
      steps.forEach((_, i) => setStep(i, ""));
      setTimer(0);
      setReplicas(3, 3);
      setEvent("steady · serving traffic");
      term.innerHTML = "";
    };
    baseline();

    if (reduceMotion) {
      term.innerHTML = TERM_SCRIPT.map((l) => (l.cmd
        ? `<span class="ln"><span class="${l.cls}">${esc(l.text)}</span><span class="t-cmd">${esc(l.cmd)}</span></span>`
        : `<span class="ln ${l.cls}">${esc(l.text)}</span>`)).join("");
      steps.forEach((_, i) => setStep(i, "done"));
      setTimer(25.5);
      setEvent("recovered in 25.5s · zero downtime", "ok");
      return;
    }

    const INC_START = 3800, INC_END = 9300, LOOP = 15500;
    let timerOn = false;
    const T = [
      [0, () => termLine("t-dim", "[hpa] watching deploy/api-gateway · 3/3 Running")],
      [1200, () => { setEvent("traffic spike · HPA scaling 3 → 5", "warn"); termLine("t-warn", "[hpa] cpu 82% > 70% target · scaling 3 → 5"); addPod(3); }],
      [1600, () => addPod(4)],
      [2500, () => { setPod(3, "ok"); setPod(4, "ok"); setReplicas(5, 5); setEvent("scaled · 5 pods running"); }],
      [INC_START, () => { setPod(1, "oom"); oomTag.show(true); setReplicas(4, 5); setEvent("incident · OOMKilled (137)", "err"); setStep(0, "active"); timerOn = true; typeCmd(); }],
      [4400, () => { scriptLine(1); scriptLine(2); spawn([E.metrics], "pk--metric", 70, () => spawn([E.alert], "pk--alert", 60)); }],
      [4900, () => scriptLine(3)],
      [5400, () => { setStep(0, "done"); setStep(1, "active"); ops.classList.add("thinking"); opsTag.set("diagnosing…"); opsTag.show(true); scriptLine(4); }],
      [6400, () => { setStep(1, "done"); setStep(2, "active"); opsTag.set("guardrail 1/2 ✓"); scriptLine(5); }],
      [7100, () => { setStep(2, "done"); setStep(3, "active"); opsTag.set("guardrail 2/2 ✓"); scriptLine(6); }],
      [7800, () => {
        setStep(3, "done"); setStep(4, "active"); ops.classList.remove("thinking"); opsTag.set("rolling restart");
        setEvent("remediating · rolling restart", "warn"); scriptLine(7);
        spawn([E.fix], "pk--fix", 150, () => { setPod(1, "term"); oomTag.show(false); });
      }],
      [9000, () => {
        if (pods[1]) { pods[1].remove(); delete pods[1]; }
        addPod(1, "pending");
        setTimeout(() => setPod(1, "ok"), 250);
        scriptLine(8);
      }],
      [INC_END, () => { setStep(4, "done"); timerOn = false; setTimer(25.5); scriptLine(9); setReplicas(5, 5); setEvent("recovered in 25.5s · zero downtime", "ok"); opsTag.show(false); }],
      [11400, () => { setEvent("load normal · HPA scaling 5 → 3"); removePod(4); }],
      [11800, () => { removePod(3); setReplicas(3, 3); }],
      [12600, () => setEvent("steady · serving traffic")],
    ];

    let t = 0, fired = 0, reqClock = 0, running = false, last = 0;
    const frame = (now) => {
      if (!running) return;
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      if (!document.hidden) {
        t += dt * 1000;
        while (fired < T.length && T[fired][0] <= t) T[fired++][1]();
        if (timerOn) setTimer(clamp((t - INC_START) / (INC_END - INC_START)) * 25.5);
        reqClock += dt;
        if (reqClock > 0.5) { reqClock = 0; spawn(requestRoute()); }
        stepPackets(dt);
        if (t >= LOOP) { t = 0; fired = 0; timerOn = false; baseline(); }
      }
      requestAnimationFrame(frame);
    };
    onVisible($(".arch"), (v) => {
      if (v && !running) { running = true; last = performance.now(); requestAnimationFrame(frame); }
      else if (!v) running = false;
    }, 0.2);
  })();

  /* ---------- Metrics: CloudWatch widgets ---------- */
  (() => {
    const widgets = $$("[data-chart]");
    const css = getComputedStyle(root);
    const tok = (n) => css.getPropertyValue(n).trim();
    const COL = { line: tok("--accent"), hi: tok("--accent-hi"), text: tok("--dim"), grid: tok("--line"), err: tok("--err") };
    const N = 60, PERIOD = 36, FIRST = 44;
    const INC = {
      latency: [420, 880, 610, 240, 150],
      rps: [1330, 1290, 1310, 1380, 1410],
      errors: [1.2, 4.8, 2.1, 0.4, 0.08],
    };
    const CFG = {
      latency: { max: 1000, ticks: [0, 500, 1000], tick: (t) => (t === 1000 ? "1s" : `${t}ms`), fmt: (v) => `${Math.round(v)} ms`, base: (k) => 118 + 14 * Math.sin(k / 5) + rnd(10), slo: 300, alarm: (v) => v > 300 },
      rps: { max: 2000, ticks: [0, 1000, 2000], tick: (t) => (t ? `${t / 1000}k` : "0"), fmt: (v) => Math.round(v).toLocaleString("en-US"), base: (k) => 1420 + 110 * Math.sin(k / 9) + rnd(40), alarm: () => false },
      errors: { max: 5, ticks: [0, 2.5, 5], tick: (t) => `${t}%`, fmt: (v) => `${v.toFixed(2)}%`, base: () => 0.03 + Math.abs(rnd(0.02)), alarm: (v) => v > 1, band: "OOMKilled → auto-healed in 25.5s" },
    };
    const incAt = (k) => { const m = (((k - FIRST) % PERIOD) + PERIOD) % PERIOD; return m < 5 ? m : -1; };
    const sample = (name, k) => { const i = incAt(k); return i >= 0 ? INC[name][i] * (1 + rnd(0.04)) : CFG[name].base(k); };
    const charts = widgets.map((w) => {
      const name = w.dataset.chart, canvas = $("canvas", w);
      return { name, canvas, ctx: canvas.getContext("2d"), cfg: CFG[name], val: $("[data-val]", w), alarm: $("[data-alarm]", w), data: [] };
    });
    let k = 0;
    for (; k < N; k++) charts.forEach((c) => c.data.push({ v: sample(c.name, k), inc: incAt(k) }));

    const draw = (c, frac) => {
      const { canvas, ctx, cfg, data } = c;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const W = canvas.clientWidth, H = canvas.clientHeight;
      if (!W) return;
      if (canvas.width !== Math.round(W * dpr) || canvas.height !== Math.round(H * dpr)) { canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr); }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      const padR = 40, padT = 8, padB = 18, iw = W - padR, ih = H - padT - padB;
      const x = (i) => (i - frac) / (N - 2) * iw;
      const y = (v) => padT + ih - Math.min(v, cfg.max) / cfg.max * ih;
      ctx.font = "10px 'Geist Mono', ui-monospace, monospace";
      ctx.textBaseline = "middle";
      cfg.ticks.forEach((tv) => {
        const yy = Math.round(y(tv)) + 0.5;
        ctx.strokeStyle = COL.grid; ctx.lineWidth = 1; ctx.setLineDash([]);
        ctx.beginPath(); ctx.moveTo(0, yy); ctx.lineTo(iw, yy); ctx.stroke();
        ctx.fillStyle = COL.text; ctx.textAlign = "left";
        ctx.fillText(cfg.tick(tv), iw + 6, yy);
      });
      ctx.textBaseline = "alphabetic";
      ctx.fillText("−5 min", 0, H - 3);
      ctx.textAlign = "right"; ctx.fillText("now", iw, H - 3);

      ctx.save();
      ctx.beginPath(); ctx.rect(0, 0, iw, H); ctx.clip();
      // incident bands; only the most recent one is annotated
      const bands = [];
      let s = -1;
      for (let i = 0; i <= data.length; i++) {
        const inc = i < data.length && data[i].inc >= 0;
        if (inc && s < 0) s = i;
        if (!inc && s >= 0) {
          const x0 = x(s - 0.5), x1 = x(i - 0.5);
          ctx.fillStyle = "rgba(207, 116, 102, 0.09)";
          ctx.fillRect(x0, padT, x1 - x0, ih);
          ctx.strokeStyle = "rgba(207, 116, 102, 0.35)"; ctx.setLineDash([2, 3]);
          ctx.beginPath(); ctx.moveTo(Math.round(x0) + 0.5, padT); ctx.lineTo(Math.round(x0) + 0.5, padT + ih); ctx.stroke();
          ctx.setLineDash([]);
          bands.push([x0, x1]);
          s = -1;
        }
      }
      if (cfg.band && bands.length) {
        const [x0, x1] = bands[bands.length - 1];
        const right = x0 > iw * 0.55;
        ctx.fillStyle = COL.err; ctx.textAlign = right ? "right" : "left"; ctx.textBaseline = "top";
        ctx.fillText(cfg.band, right ? x0 - 6 : x1 + 6, padT + 2);
        ctx.textBaseline = "alphabetic";
      }
      if (cfg.slo) {
        const yy = Math.round(y(cfg.slo)) + 0.5;
        ctx.strokeStyle = COL.err; ctx.globalAlpha = 0.6; ctx.setLineDash([4, 4]);
        ctx.beginPath(); ctx.moveTo(0, yy); ctx.lineTo(iw, yy); ctx.stroke();
        ctx.setLineDash([]); ctx.globalAlpha = 1;
        ctx.fillStyle = COL.err; ctx.textAlign = "left"; ctx.fillText("SLO 300ms", 4, yy - 5);
      }
      const grad = ctx.createLinearGradient(0, padT, 0, padT + ih);
      grad.addColorStop(0, "rgba(201, 204, 211, 0.22)");
      grad.addColorStop(1, "rgba(201, 204, 211, 0)");
      ctx.beginPath();
      data.forEach((p, i) => (i ? ctx.lineTo(x(i), y(p.v)) : ctx.moveTo(x(i), y(p.v))));
      ctx.lineTo(x(data.length - 1), padT + ih); ctx.lineTo(x(0), padT + ih); ctx.closePath();
      ctx.fillStyle = grad; ctx.fill();
      ctx.beginPath();
      data.forEach((p, i) => (i ? ctx.lineTo(x(i), y(p.v)) : ctx.moveTo(x(i), y(p.v))));
      ctx.strokeStyle = COL.line; ctx.lineWidth = 1.5; ctx.lineJoin = "round"; ctx.stroke();
      ctx.restore();
      const lx = x(data.length - 1), ly = y(data[data.length - 1].v);
      if (lx <= iw + 0.5) {
        ctx.fillStyle = COL.hi; ctx.beginPath(); ctx.arc(lx, ly, 3, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = "rgba(244, 245, 247, 0.25)"; ctx.lineWidth = 4; ctx.beginPath(); ctx.arc(lx, ly, 6, 0, Math.PI * 2); ctx.stroke();
      }
    };
    const readout = (c) => {
      const v = c.data[c.data.length - 1].v;
      c.val.textContent = c.cfg.fmt(v);
      const alarm = c.cfg.alarm(v);
      c.alarm.textContent = alarm ? "ALARM" : "OK";
      c.alarm.classList.toggle("is-alarm", alarm);
    };
    const drawAll = (frac) => charts.forEach((c) => draw(c, frac));
    charts.forEach(readout);
    drawAll(1);
    window.addEventListener("resize", () => drawAll(1));
    document.fonts && document.fonts.ready.then(() => drawAll(1));
    if (reduceMotion) return;

    let running = false, lastTick = 0;
    const frame = (now) => {
      if (!running) return;
      if (!document.hidden) {
        if (now - lastTick >= 1000) {
          lastTick = now;
          charts.forEach((c) => { c.data.push({ v: sample(c.name, k), inc: incAt(k) }); c.data.shift(); readout(c); });
          k++;
        }
        drawAll(clamp((now - lastTick) / 1000));
      }
      requestAnimationFrame(frame);
    };
    onVisible($(".cw"), (v) => {
      if (v && !running) { running = true; lastTick = performance.now(); requestAnimationFrame(frame); }
      else if (!v) running = false;
    }, 0.05);
  })();

  /* ---------- Metrics: MTTR before/after (scroll-scrubbed when pinned) ---------- */
  (() => {
    const pin = $("#pin"), panel = $("#mttr");
    const big = $("#mttrBig"), bar = $("#mttrBar"), small = $("#mttrSmall"), note = $("#mttrNote");
    const FROM = 2700, TO = 25.5;
    const fmt = (s) => { const m = Math.floor(s / 60); return `${pad(m)}:${(s - m * 60).toFixed(1).padStart(4, "0")}`; };
    const render = (p) => {
      const e = 1 - Math.pow(1 - p, 3);
      const s = FROM + (TO - FROM) * e;
      big.textContent = fmt(s);
      bar.style.width = `${(s / FROM) * 100}%`;
      small.textContent = s >= 90 ? `${Math.round(s / 60)} min` : `${s.toFixed(1)} s`;
      panel.classList.toggle("is-done", p >= 1);
      note.textContent = p > 0.5 ? "detect → diagnose → 2 guardrails → rolling restart" : "page on-call → ssh → grep logs → guess → restart";
    };
    if (reduceMotion) return render(1);
    const mq = window.matchMedia("(min-width: 1025px) and (min-height: 760px)");
    if (mq.matches) {
      pin.classList.add("is-pinned");
      const update = () => {
        const r = pin.getBoundingClientRect();
        const total = pin.offsetHeight - window.innerHeight;
        const p = total > 0 ? clamp(-r.top / total) : 1;
        render(clamp((p - 0.1) / 0.65));
      };
      scrollFns.push(update);
      update();
    } else {
      render(0);
      let played = false;
      onVisible(panel, (v) => {
        if (!v || played) return;
        played = true;
        const start = performance.now();
        const step = (now) => { const p = clamp((now - start) / 2600); render(p); if (p < 1) requestAnimationFrame(step); };
        requestAnimationFrame(step);
      }, 0.5);
    }
  })();

  /* ---------- Pipeline: GitHub Actions run ---------- */
  (() => {
    const box = $("#gha");
    const logEl = $("#ghaLog"), jobEl = $("#ghaJob"), totalEl = $("#ghaTotal"), stateEl = $("#ghaState");
    const statusEl = $("#ghaStatus"), numEl = $("#ghaNum"), shaEl = $("#ghaSha");
    const node = (id) => $(`.gnode[data-job="${id}"]`, box);
    const JOBS = [
      { id: "tests", name: "Tests", dur: 18, log: ["Run actions/checkout@v4", "Run pip install -r requirements.txt", "Run ruff check .", "All checks passed!", "Run pytest -q", "✓ unit tests passed"] },
      { id: "docker", name: "Docker build", dur: 42, log: ["Run docker/setup-buildx-action@v3", "Run docker buildx build --target runtime -t opsmind/api:{sha} .", "#6 [builder 2/4] COPY requirements.txt .", "#7 [builder 3/4] RUN pip install --no-cache-dir -r requirements.txt", "#9 [runtime 2/2] COPY --from=builder /install /usr/local", "✓ pushed opsmind/api:{sha}"] },
      { id: "terraform", name: "Terraform", dur: 24, log: ["Run terraform init", "Terraform has been successfully initialized!", "Run terraform plan -out=tfplan", "Plan: 0 to add, 1 to change, 0 to destroy.", "Run terraform apply -auto-approve tfplan", "✓ Apply complete! Resources: 0 added, 1 changed, 0 destroyed."] },
      { id: "deploy", name: "K8s deploy", dur: 31, log: ["Run kubectl set image deploy/api api=opsmind/api:{sha}", "deployment.apps/api image updated", "Waiting for rollout: 1 of 3 updated replicas are available...", "Waiting for rollout: 2 of 3 updated replicas are available...", "✓ deployment \"api\" successfully rolled out"] },
      { id: "health", name: "Health check", dur: 8, log: ["Run curl -fsS http://44.210.213.12/healthz", "HTTP/1.1 200 OK · 14 ms", "readiness probes: 3/3 ready", "✓ Live · 99.99% uptime"] },
    ];
    let lineNo = 0, run = 214, total = 0, sha = "3f9c2ab";
    const newSha = () => Math.random().toString(16).slice(2, 9);
    const log = (text, cls = "") => {
      const s = document.createElement("span");
      s.className = `ln ${cls}`;
      s.innerHTML = `<b>${++lineNo}</b>`;
      s.appendChild(document.createTextNode(text.replace(/\{sha\}/g, sha)));
      logEl.appendChild(s);
      while (logEl.children.length > 40) logEl.firstChild.remove();
    };
    const lineClass = (l) => (l.startsWith("Run ") ? "cmd" : l.startsWith("✓") ? "ok" : "");
    const setNode = (id, s) => { node(id).dataset.s = s; };
    const setRunState = (s) => { statusEl.dataset.s = s; stateEl.textContent = s === "done" ? "Success" : "In progress"; };
    const reset = () => {
      $$(".gnode", box).forEach((n) => { n.dataset.s = "queued"; });
      $$(".gnode__d", box).forEach((d) => { d.textContent = ""; });
      logEl.innerHTML = ""; lineNo = 0; total = 0;
      totalEl.textContent = "0s";
      numEl.textContent = `#${run}`; shaEl.textContent = sha;
      setRunState("running");
    };

    if (reduceMotion) {
      reset();
      $$(".gnode", box).forEach((n) => { n.dataset.s = "done"; });
      JOBS.forEach((j) => { $(".gnode__d", node(j.id)).textContent = `${j.dur}s`; });
      jobEl.textContent = "Health check";
      JOBS[4].log.forEach((l) => log(l, lineClass(l)));
      totalEl.textContent = `${JOBS.reduce((a, j) => a + j.dur, 0)}s`;
      setRunState("done");
      return;
    }

    let live = false;
    onVisible(box, (v) => { live = v; }, 0.2);
    const wait = (ms) => pausableWait(ms, () => live);
    const play = async () => {
      for (;;) {
        reset();
        await wait(600);
        setNode("push", "done"); log(`Triggered via push to main · ${sha} by Rodevops07`, "grp");
        await wait(500);
        setNode("actions", "done"); log("Workflow deploy.yml · 5 jobs queued", "grp");
        for (const j of JOBS) {
          setNode(j.id, "running");
          jobEl.textContent = j.name;
          log(`▾ ${j.name}`, "grp");
          const d = $(".gnode__d", node(j.id));
          for (let i = 0; i < j.log.length; i++) {
            await wait(360 + Math.random() * 220);
            log(j.log[i], lineClass(j.log[i]));
            d.textContent = `${Math.round(j.dur * (i + 1) / j.log.length)}s`;
            total += j.dur / j.log.length;
            totalEl.textContent = `${Math.round(total)}s`;
          }
          setNode(j.id, "done");
        }
        await wait(400);
        setNode("live", "done");
        setRunState("done");
        await wait(5200);
        run++; sha = newSha();
      }
    };
    play();
  })();

  /* ---------- Contact form (opens mail client, no backend needed) ---------- */
  const form = $("#contactForm");
  const status = $("#formStatus");
  const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    const checks = {
      name: data.name.trim().length > 1,
      email: emailRe.test(data.email.trim()),
      message: data.message.trim().length > 4,
    };
    let valid = true;
    Object.entries(checks).forEach(([key, ok]) => {
      form.elements[key].closest(".field").classList.toggle("is-invalid", !ok);
      if (!ok) valid = false;
    });
    status.className = "form__status mono";
    if (!valid) {
      status.textContent = "✖ please fill in a name, a valid email and a message.";
      status.classList.add("is-err");
      return;
    }
    const subject = encodeURIComponent(`Portfolio contact from ${data.name.trim()}`);
    const body = encodeURIComponent(`${data.message.trim()}\n\n— ${data.name.trim()} (${data.email.trim()})`);
    window.location.href = `mailto:${EMAIL}?subject=${subject}&body=${body}`;
    status.textContent = "✔ opening your mail app… if nothing opens, email rohitpujari7114@gmail.com directly.";
    status.classList.add("is-ok");
    form.reset();
  });

  $$(".field input, .field textarea", form).forEach((el) =>
    el.addEventListener("input", () => el.closest(".field").classList.remove("is-invalid")));

  /* ---------- Copy email ---------- */
  const copyBtn = $("#copyEmail");
  const copyEmail = async () => {
    const label = $("span", copyBtn);
    try {
      await navigator.clipboard.writeText(EMAIL);
      label.textContent = "copied";
    } catch {
      const range = document.createRange();
      range.selectNodeContents($(".contact__email"));
      const sel = window.getSelection();
      sel.removeAllRanges(); sel.addRange(range);
      label.textContent = "selected";
    }
    setTimeout(() => { label.textContent = "copy"; }, 1800);
  };
  copyBtn.addEventListener("click", copyEmail);

  /* ---------- Command palette (Ctrl/⌘ + K) ---------- */
  (() => {
    const pal = $("#palette"), input = $("#paletteInput"), list = $("#paletteList");
    const go = (hash) => () => $(hash).scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
    const openLink = (href, download) => () => {
      const a = document.createElement("a");
      a.href = href;
      if (download) a.download = ""; else { a.target = "_blank"; a.rel = "noopener"; }
      document.body.appendChild(a); a.click(); a.remove();
    };
    const ITEMS = [
      ["Jump to", "Home", "#home", "hero console top"],
      ["Jump to", "About", "#about", "bio stats photo"],
      ["Jump to", "Architecture & self-healing", "#systems", "systems aws vpc ec2 kubernetes k8s pods opsmind"],
      ["Jump to", "CloudWatch dashboard", "#metrics", "metrics mttr latency observability"],
      ["Jump to", "CI/CD pipeline", "#pipeline", "github actions deploy terraform docker"],
      ["Jump to", "Skills", "#skills", "arsenal stack tools"],
      ["Jump to", "Projects", "#projects", "opsmind chaos lab deployment"],
      ["Jump to", "Contact", "#contact", "email hire message"],
    ].map(([group, label, hash, kw]) => ({ group, label, kw, icon: "i-hash", hint: hash, run: go(hash) })).concat([
      { group: "Actions", label: "Ask Ro's AI", kw: "chat assistant question", icon: "i-spark", run: () => window.RoAI.open() },
      { group: "Actions", label: "Copy email address", kw: "mail contact", icon: "i-copy", hint: EMAIL, run: copyEmail },
      { group: "Actions", label: "Open GitHub · Rodevops07", kw: "code repos", icon: "i-github", run: openLink("https://github.com/Rodevops07") },
      { group: "Actions", label: "Open LinkedIn", kw: "profile", icon: "i-linkedin", run: openLink("https://www.linkedin.com/in/rohit-pujari-149723273") },
      { group: "Actions", label: "WhatsApp Rohit", kw: "phone call message chat", icon: "i-whatsapp", hint: "+91 78409 38958", run: openLink("https://wa.me/917840938958") },
      { group: "Actions", label: "Open Instagram", kw: "insta social", icon: "i-instagram", hint: "ro_pujari_xxiv.07", run: openLink("https://www.instagram.com/ro_pujari_xxiv.07") },
      { group: "Actions", label: "Open OpsMind live app", kw: "demo aws", icon: "i-external", run: openLink("http://44.210.213.12:3000") },
      { group: "Actions", label: "Download resume", kw: "cv pdf", icon: "i-download", run: openLink("assets/Rohit_Pujari_Resume.pdf", true) },
    ]);
    let shown = [], sel = 0, lastFocus = null;
    const escHtml = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const render = () => {
      const q = input.value.trim().toLowerCase();
      shown = ITEMS.filter((it) => !q || `${it.label} ${it.kw}`.toLowerCase().includes(q));
      if (q) {
        const raw = input.value.trim();
        const ask = { group: "Ask the AI", label: `Ask Ro's AI: “${raw}”`, icon: "i-spark", run: () => window.RoAI.open(raw) };
        shown = shown.length ? shown.concat(ask) : [ask];
      }
      sel = Math.min(sel, shown.length - 1);
      let html = "", group = "";
      shown.forEach((it, i) => {
        if (it.group !== group) { group = it.group; html += `<li class="palette__group" role="presentation">${escHtml(group)}</li>`; }
        html += `<li class="palette__item" role="option" id="pal-${i}" data-i="${i}" aria-selected="${i === sel}"><svg class="ic"><use href="#${it.icon}"/></svg><span>${escHtml(it.label)}</span>${it.hint ? `<small>${escHtml(it.hint)}</small>` : ""}</li>`;
      });
      list.innerHTML = html;
      input.setAttribute("aria-activedescendant", `pal-${sel}`);
      const cur = $(`#pal-${sel}`, list);
      if (cur) cur.scrollIntoView({ block: "nearest" });
    };
    const open = () => {
      if (!pal.hidden) return;
      lastFocus = document.activeElement;
      pal.hidden = false;
      input.value = ""; sel = 0; render();
      setTimeout(() => input.focus(), 10);
    };
    const close = (restore = true) => {
      if (pal.hidden) return;
      pal.hidden = true;
      if (restore && lastFocus) lastFocus.focus();
    };
    const exec = (i) => { const it = shown[i]; if (!it) return; close(false); it.run(); };
    input.addEventListener("input", () => { sel = 0; render(); });
    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") { e.preventDefault(); sel = (sel + 1) % shown.length; render(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); sel = (sel - 1 + shown.length) % shown.length; render(); }
      else if (e.key === "Enter") { e.preventDefault(); exec(sel); }
      else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); }
      else if (e.key === "Tab") e.preventDefault();
    });
    list.addEventListener("click", (e) => { const li = e.target.closest(".palette__item"); if (li) exec(+li.dataset.i); });
    list.addEventListener("pointermove", (e) => {
      const li = e.target.closest(".palette__item");
      if (li && +li.dataset.i !== sel) { sel = +li.dataset.i; render(); }
    });
    $$("[data-palette-open]").forEach((b) => b.addEventListener("click", open));
    $$("[data-palette-close]").forEach((b) => b.addEventListener("click", () => close()));
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); pal.hidden ? open() : close(); }
    });
    const kbd = $(".kbar-btn kbd");
    if (/Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)) {
      kbd.textContent = "⌘K";
      $$(".footer__hint kbd").forEach((k) => { k.textContent = "⌘K"; });
    }
  })();
})();

/* ================= AI assistant ================= */
(() => {
  "use strict";

  // Serverless endpoint (see api/chat.js). If it's unreachable, the assistant
  // falls back to answering from the built-in profile knowledge base below.
  const AI_ENDPOINT = "/api/chat";

  const fab = document.getElementById("aiFab");
  const panel = document.getElementById("aiPanel");
  const closeBtn = document.getElementById("aiClose");
  const log = document.getElementById("aiLog");
  const form = document.getElementById("aiForm");
  const input = document.getElementById("aiInput");
  const chips = document.getElementById("aiChips");
  const mode = document.getElementById("aiMode");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const history = [];
  let apiAvailable = location.protocol !== "file:";
  let busy = false;
  let greeted = false;

  const setMode = (live) => {
    mode.innerHTML = live
      ? '<span class="dot"></span> Groq Llama-3 · live'
      : '<span class="dot dot--idle"></span> profile knowledge mode';
  };

  const open = (question) => {
    panel.hidden = false;
    fab.setAttribute("aria-expanded", "true");
    if (!greeted) {
      greeted = true;
      addBot("Hey! 👋 I'm Ro's AI assistant. Ask me anything about Rohit's cloud & DevOps skills, projects like OpsMind, or how to hire him.", false);
    }
    if (question) ask(question);
    else setTimeout(() => input.focus(), 50);
  };
  const close = () => {
    panel.hidden = true;
    fab.setAttribute("aria-expanded", "false");
    fab.focus();
  };
  window.RoAI = { open };

  fab.addEventListener("click", () => open());
  closeBtn.addEventListener("click", close);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) close(); });
  document.querySelectorAll("[data-ai-open]").forEach((btn) =>
    btn.addEventListener("click", () => open(btn.dataset.aiAsk)));
  chips.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) ask(b.textContent);
  });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (q) ask(q);
  });

  const scrollDown = () => { log.scrollTop = log.scrollHeight; };
  const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const linkify = (s) => escapeHtml(s)
    .replace(/(https?:\/\/[^\s)]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>')
    .replace(/([\w.+-]+@[\w-]+\.[\w.]+)/g, '<a href="mailto:$1">$1</a>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  const addUser = (text) => {
    const el = document.createElement("div");
    el.className = "msg msg--user";
    el.textContent = text;
    log.appendChild(el);
    scrollDown();
  };

  const addBot = (text, animate = true) => {
    const el = document.createElement("div");
    el.className = "msg msg--bot";
    log.appendChild(el);
    if (!animate || reduceMotion) { el.innerHTML = linkify(text); scrollDown(); return Promise.resolve(); }
    return new Promise((resolve) => {
      let i = 0;
      const step = () => {
        i = Math.min(text.length, i + 3);
        el.textContent = text.slice(0, i).replace(/\*\*/g, "");
        scrollDown();
        if (i < text.length) requestAnimationFrame(step);
        else { el.innerHTML = linkify(text); scrollDown(); resolve(); }
      };
      step();
    });
  };

  const showTyping = () => {
    const el = document.createElement("div");
    el.className = "msg msg--bot";
    el.innerHTML = '<span class="typing"><i></i><i></i><i></i></span>';
    log.appendChild(el);
    scrollDown();
    return el;
  };

  const askApi = async () => {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 15000);
    try {
      const res = await fetch(AI_ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history.slice(-10) }),
        signal: ctrl.signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data || typeof data.reply !== "string" || !data.reply.trim()) throw new Error("empty reply");
      return data.reply.trim();
    } finally {
      clearTimeout(timer);
    }
  };

  async function ask(question) {
    if (busy) return;
    busy = true;
    form.querySelector("button").disabled = true;
    input.value = "";
    addUser(question);
    history.push({ role: "user", content: question });
    const typing = showTyping();

    let reply;
    if (apiAvailable) {
      try {
        reply = await askApi();
        setMode(true);
      } catch {
        apiAvailable = false;
      }
    }
    if (!reply) {
      setMode(false);
      await new Promise((r) => setTimeout(r, 500 + Math.random() * 500));
      reply = localAnswer(question);
    }

    typing.remove();
    history.push({ role: "assistant", content: reply });
    await addBot(reply);
    busy = false;
    form.querySelector("button").disabled = false;
    input.focus();
  }

  /* ---------- Built-in profile knowledge base (fallback) ---------- */
  const KB = [
    { k: ["opsmind", "aiops", "self-heal", "self heal", "heal", "remediat", "groq", "llama"],
      a: "**OpsMind** is Rohit's autonomous AIOps & cloud reliability platform running on AWS EC2. It ingests public repos, auto-generates multi-stage Dockerfiles and Kubernetes manifests, injects chaos faults (OOMKilled, CPU throttling, missing configs, 100GB exploits) and auto-remediates outages using Groq Llama-3 plus 2-stage deterministic safety guardrails.\n\nImpact: MTTR cut from 45 min to 25.5 s (98.6% reduction), with a strict 2GB memory ceiling against malicious exploits.\n\nCode: https://github.com/Rodevops07/OpsMind\nLive: http://44.210.213.12:3000" },
    { k: ["mttr", "recovery", "25.5", "incident"],
      a: "Rohit's OpsMind platform recovers from incidents automatically in **25.5 seconds** — down from ~45 minutes of manual recovery, a 98.6% MTTR reduction." },
    { k: ["pipeline", "ci/cd", "cicd", "deployment", "deploy", "oauth", "nginx", "github actions", "jenkins"],
      a: "Rohit built an **Automated Microservices Cloud Deployment Pipeline** on AWS EC2: multi-tenant GitHub OAuth, reverse-proxy ingress routing with Nginx, systemd-managed services and persistent EBS volume mounts. He works with GitHub Actions, Jenkins, Terraform and Git for CI/CD.\n\nRepo: https://github.com/Rodevops07/automated-deployment" },
    { k: ["chaos", "benchmark", "137", "oom", "cgroup", "throttl", "prometheus", "security lab"],
      a: "The **Chaos Security Lab** is a 20-scenario empirical chaos testing engine. It simulates Linux kernel memory saturation (exit code 137), CPU throttling and resource-exhaustion attacks to measure cloud defense resilience and MTTR telemetry — built with Python, Linux cgroups, the Kubernetes API and Prometheus." },
    { k: ["kubernetes", "k8s", "pod", "ingress", "helm", "orchestrat"],
      a: "Rohit works hands-on with **Kubernetes** — Pods, Deployments, Services, Ingress and cgroup resource limits. OpsMind auto-generates K8s YAML manifests and performs zero-downtime rolling restarts to heal failing pods." },
    { k: ["docker", "container", "compose"],
      a: "Rohit containerizes workloads with **Docker** and Docker Compose, including auto-generated multi-stage Dockerfiles for lean, secure production images." },
    { k: ["aws", "ec2", "s3", "vpc", "iam", "cloudwatch", "ebs", "elastic ip", "cloud"],
      a: "On **AWS** Rohit works with EC2, Elastic IP, EBS, S3, VPC, Security Groups, IAM and CloudWatch — architecting and deploying production workloads with 99.99% uptime." },
    { k: ["terraform", "iac", "infrastructure as code"],
      a: "Rohit uses **Terraform** for Infrastructure as Code, alongside GitHub Actions and Jenkins for automated delivery." },
    { k: ["linux", "bash", "shell", "ubuntu", "debian", "ssh", "dns", "network"],
      a: "Rohit is strong in **Linux** (Ubuntu/Debian) system administration, Shell & Bash scripting, reverse-proxy ingress, DNS management and SSH." },
    { k: ["python", "fastapi", "node", "next", "program", "language", "code"],
      a: "Rohit codes in **Python (FastAPI)**, Bash, Next.js and Node.js — OpsMind's backend is FastAPI and its dashboard is Next.js." },
    { k: ["skill", "stack", "tech", "tools", "specializ", "expert", "good at", "what does he do", "arsenal"],
      a: "Rohit specializes in **cloud infrastructure, DevOps automation and SRE**:\n• Cloud: AWS (EC2, EBS, S3, VPC, IAM, CloudWatch)\n• Containers: Docker, Kubernetes\n• CI/CD: GitHub Actions, Jenkins, Terraform, Git\n• OS: Linux, Bash, Nginx, DNS, SSH\n• Code: Python FastAPI, Next.js, Node.js\n• Reliability: Chaos Engineering, AI diagnostics, safety guardrails" },
    { k: ["experience", "years", "background", "about", "who is", "who's", "tell me about him", "rohit"],
      a: "Rohit Pujari (Ro) is a Cloud & DevOps Engineer and SRE specialist with **1+ year of hands-on experience** architecting, automating and deploying production workloads on AWS. He focuses on zero-downtime releases, eliminating manual toil and building self-healing systems — maintaining 99.99% uptime." },
    { k: ["hire", "open to", "available", "job", "role", "work", "opportunit", "recruit"],
      a: "Yes — Rohit is **currently open to Cloud Engineer, DevOps Engineer and Site Reliability Engineer (SRE) roles**. Reach him at rohitpujari7114@gmail.com, on WhatsApp (+91 78409 38958) or on LinkedIn: https://www.linkedin.com/in/rohit-pujari-149723273" },
    { k: ["contact", "email", "mail", "reach", "linkedin", "github", "phone", "connect", "whatsapp", "number", "instagram", "insta"],
      a: "You can reach Rohit at rohitpujari7114@gmail.com\nPhone / WhatsApp: +91 78409 38958 (https://wa.me/917840938958)\nInstagram: https://www.instagram.com/ro_pujari_xxiv.07\nLinkedIn: https://www.linkedin.com/in/rohit-pujari-149723273\nGitHub: https://github.com/Rodevops07" },
    { k: ["where", "location", "based", "city", "mumbai", "palghar", "india", "remote", "relocat"],
      a: "Rohit is based in **Palghar / Mumbai, Maharashtra, India**." },
    { k: ["resume", "cv"],
      a: "You can download Rohit's resume with the **Download Resume** button at the top of the page, or email him at rohitpujari7114@gmail.com." },
    { k: ["uptime", "99.99", "availability", "guardrail", "stat"],
      a: "Key numbers: **99.99%** cloud uptime maintained · **25.5s** automated incident recovery · **20+** chaos scenarios benchmarked · **100%** deterministic guardrail security." },
    { k: ["project", "portfolio", "built", "work on"],
      a: "Rohit's featured projects:\n1. **OpsMind** — autonomous AIOps self-healing platform (MTTR 45 min → 25.5 s)\n2. **Automated Microservices Deployment Pipeline** on AWS\n3. **Chaos Security Lab** — 20-scenario chaos benchmark suite\n\nAsk me about any of them!" },
    { k: ["hi", "hello", "hey", "namaste", "yo"],
      a: "Hey! 👋 Ask me about Rohit's skills, projects (like OpsMind), experience, or how to get in touch." },
  ];

  function localAnswer(q) {
    const text = ` ${q.toLowerCase()} `;
    let best = null, bestScore = 0;
    for (const entry of KB) {
      const score = entry.k.reduce((s, kw) => {
        const hit = kw.length <= 3 ? new RegExp(`\\b${kw}\\b`).test(text) : text.includes(kw);
        return s + (hit ? kw.length : 0);
      }, 0);
      if (score > bestScore) { best = entry; bestScore = score; }
    }
    return best
      ? best.a
      : "I'm focused on Rohit's professional profile — try asking about his AWS, Kubernetes or CI/CD skills, the OpsMind project, or whether he's open to work. You can also email him directly at rohitpujari7114@gmail.com.";
  }
})();
