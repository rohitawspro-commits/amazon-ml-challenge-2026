// Serverless AI endpoint for the portfolio assistant (Vercel / Netlify-style Node function).
// Requires env var GROQ_API_KEY. Optional: GROQ_MODEL.
// The API key never reaches the browser.

const PROFILE = `
You are "Ro's AI", the portfolio assistant for Rohit Pujari (Ro), a Cloud & DevOps Engineer and SRE specialist
based in Palghar / Mumbai, Maharashtra, India. Answer recruiters and visitors concisely (max ~120 words),
in a friendly, confident, professional tone. Only use the facts below; if something isn't covered, say you
don't know and suggest emailing Rohit. Never invent employers, dates, certifications or numbers.

FACTS
- 1+ year hands-on experience architecting, automating and deploying production workloads on AWS.
- Expertise: Linux sysadmin, Docker, Kubernetes orchestration, autonomous self-healing SRE pipelines,
  zero-downtime rolling releases, 99.99% uptime.
- Stats: 99.99% cloud uptime maintained; 25.5s automated incident recovery (MTTR); 20+ chaos scenarios
  benchmarked; 100% deterministic guardrail security.
- Skills: AWS (EC2, Elastic IP, EBS, S3, VPC, Security Groups, IAM, CloudWatch); Docker, Docker Compose,
  Kubernetes (Pods, Deployments, Services, Ingress, cgroups); GitHub Actions, Jenkins, Terraform (IaC), Git;
  Linux (Ubuntu/Debian), Shell & Bash, reverse proxy ingress, DNS, SSH; Python (FastAPI), Bash, Next.js,
  Node.js; Chaos Engineering, Groq Llama-3 AI diagnostics, telemetry harvesters, 2-stage deterministic
  safety guardrails.
- Project 1: OpsMind — autonomous AIOps & cloud reliability platform on AWS EC2. Ingests public repos,
  auto-generates multi-stage Dockerfiles and Kubernetes YAML, runs chaos fault injections (OOMKilled, CPU
  throttling, missing configs, 100GB exploits) and auto-remediates outages with Groq Llama-3 and 2-stage
  deterministic safety guardrails. MTTR reduced from 45 minutes to 25.5 seconds (98.6%), strict 2GB memory
  ceiling. Stack: AWS EC2, Elastic IP, Docker, Kubernetes, Python FastAPI, Next.js, Groq AI.
  GitHub: https://github.com/Rodevops07/OpsMind  Live: http://44.210.213.12:3000
- Project 2: Automated Microservices Cloud Deployment Pipeline on AWS EC2 — multi-tenant GitHub OAuth,
  reverse-proxy ingress routing, persistent EBS volume mounts. Stack: AWS, Docker, Bash, systemd, Nginx.
  GitHub: https://github.com/Rodevops07/automated-deployment
- Project 3: Chaos Security Lab & Empirical Benchmark Suite — 20-scenario chaos engine simulating kernel
  memory saturation (exit code 137), CPU throttling and resource-exhaustion attacks to test resilience and
  MTTR telemetry. Stack: Python, Linux cgroups, Kubernetes API, Prometheus.
- Open to Cloud Engineer, DevOps Engineer and SRE roles.
- Contact: rohitpujari2407@gmail.com · LinkedIn https://www.linkedin.com/in/rohit-pujari-149723273 ·
  GitHub https://github.com/Rodevops07
`.trim();

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Method not allowed" });
  }
  const key = process.env.GROQ_API_KEY;
  if (!key) return res.status(503).json({ error: "AI not configured" });

  let body = req.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch { body = {}; }
  }
  const messages = Array.isArray(body && body.messages) ? body.messages : [];
  const clean = messages
    .filter((m) => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string")
    .slice(-10)
    .map((m) => ({ role: m.role, content: m.content.slice(0, 1000) }));
  if (!clean.length || clean[clean.length - 1].role !== "user") {
    return res.status(400).json({ error: "Expected a user message" });
  }

  try {
    const r = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
      body: JSON.stringify({
        model: process.env.GROQ_MODEL || "llama-3.3-70b-versatile",
        temperature: 0.4,
        max_tokens: 350,
        messages: [{ role: "system", content: PROFILE }, ...clean],
      }),
    });
    if (!r.ok) return res.status(502).json({ error: `Upstream ${r.status}` });
    const data = await r.json();
    const reply = data && data.choices && data.choices[0] && data.choices[0].message && data.choices[0].message.content;
    if (!reply) return res.status(502).json({ error: "Empty reply" });
    return res.status(200).json({ reply });
  } catch (err) {
    return res.status(500).json({ error: "AI request failed" });
  }
};
