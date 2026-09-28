(() => {
  "use strict";

  const EMAIL = "rohitpujari2407@gmail.com";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  $("#year").textContent = new Date().getFullYear();

  /* ---------- Nav: scrolled state, progress bar, mobile menu ---------- */
  const nav = $("#nav");
  const toggle = $("#navToggle");
  const links = $("#navLinks");
  const progress = $(".scroll-progress");

  let ticking = false;
  const onScroll = () => {
    const y = window.scrollY;
    nav.classList.toggle("is-scrolled", y > 20);
    const max = document.documentElement.scrollHeight - window.innerHeight;
    progress.style.transform = `scaleX(${max > 0 ? y / max : 0})`;
    ticking = false;
  };
  window.addEventListener("scroll", () => {
    if (!ticking) { requestAnimationFrame(onScroll); ticking = true; }
  }, { passive: true });
  onScroll();

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
  $$("section[id]").forEach((s) => sectionObserver.observe(s));

  /* ---------- Reveal on scroll (with sibling stagger) ---------- */
  const revealEls = $$(".reveal");
  revealEls.forEach((el) => {
    const siblings = [...el.parentElement.children].filter((c) => c.classList.contains("reveal"));
    el.style.setProperty("--d", `${Math.min(siblings.indexOf(el), 6) * 0.08}s`);
  });
  const revealObserver = new IntersectionObserver((entries, obs) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-visible");
      obs.unobserve(entry.target);
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
  revealEls.forEach((el) => revealObserver.observe(el));

  /* ---------- Stat counters ---------- */
  const animateCount = (el) => {
    const target = parseFloat(el.dataset.count);
    const decimals = parseInt(el.dataset.decimals || "0", 10);
    if (reduceMotion) { el.textContent = target.toFixed(decimals); return; }
    const duration = 1600;
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
      animateCount(entry.target);
      obs.unobserve(entry.target);
    });
  }, { threshold: 0.6 });
  $$("[data-count]").forEach((el) => countObserver.observe(el));

  /* ---------- Card spotlight follows cursor ---------- */
  $$(".skill, .project").forEach((card) => {
    card.addEventListener("pointermove", (e) => {
      const r = card.getBoundingClientRect();
      card.style.setProperty("--mx", `${e.clientX - r.left}px`);
      card.style.setProperty("--my", `${e.clientY - r.top}px`);
    });
  });

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
    setTimeout(tick, 2600);
  }

  /* ---------- Terminal: self-healing incident replay ---------- */
  const term = $("#terminal");
  const script = [
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
  const esc = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  const renderStatic = () => {
    term.innerHTML = script.map((l) =>
      l.cmd ? `<span class="${l.cls}">${esc(l.text)}</span><span class="t-cmd">${esc(l.cmd)}</span>`
            : `<span class="${l.cls}">${esc(l.text)}</span>`).join("\n");
  };

  const playTerminal = async () => {
    const wait = (ms) => new Promise((res) => setTimeout(res, ms));
    while (true) {
      term.innerHTML = "";
      for (const line of script) {
        const row = document.createElement("span");
        if (line.cmd) {
          row.innerHTML = `<span class="${line.cls}">${esc(line.text)}</span><span class="t-cmd"></span>`;
          term.appendChild(row);
          const cmdEl = row.lastChild;
          for (const ch of line.cmd) { cmdEl.textContent += ch; await wait(38); }
          await wait(350);
        } else {
          row.className = line.cls;
          row.textContent = line.text;
          term.appendChild(row);
          await wait(420);
        }
        term.appendChild(document.createTextNode("\n"));
      }
      await wait(5000);
    }
  };
  reduceMotion ? renderStatic() : playTerminal();

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
    status.textContent = "✔ opening your mail app… if nothing opens, email rohitpujari2407@gmail.com directly.";
    status.classList.add("is-ok");
    form.reset();
  });

  $$(".field input, .field textarea", form).forEach((el) =>
    el.addEventListener("input", () => el.closest(".field").classList.remove("is-invalid")));
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
      : '<span class="dot" style="background:#fbbf24;box-shadow:0 0 10px #fbbf24"></span> profile knowledge mode';
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
      a: "Yes — Rohit is **currently open to Cloud Engineer, DevOps Engineer and Site Reliability Engineer (SRE) roles**. Reach him at rohitpujari2407@gmail.com or on LinkedIn: https://www.linkedin.com/in/rohit-pujari-149723273" },
    { k: ["contact", "email", "mail", "reach", "linkedin", "github", "phone", "connect"],
      a: "You can reach Rohit at rohitpujari2407@gmail.com\nLinkedIn: https://www.linkedin.com/in/rohit-pujari-149723273\nGitHub: https://github.com/Rodevops07" },
    { k: ["where", "location", "based", "city", "mumbai", "palghar", "india", "remote", "relocat"],
      a: "Rohit is based in **Palghar / Mumbai, Maharashtra, India**." },
    { k: ["resume", "cv"],
      a: "You can download Rohit's resume with the **Download Resume** button at the top of the page, or email him at rohitpujari2407@gmail.com." },
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
      : "I'm focused on Rohit's professional profile — try asking about his AWS, Kubernetes or CI/CD skills, the OpsMind project, or whether he's open to work. You can also email him directly at rohitpujari2407@gmail.com.";
  }
})();
