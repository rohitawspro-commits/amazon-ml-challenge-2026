"""Writes the four RailTrack API documentation pages with the same header, menu and footer."""
PAGES = [("index.html", "Overview"), ("getting-started.html", "Getting Started"),
         ("endpoints.html", "Endpoints"), ("faq.html", "Errors &amp; FAQ")]
CURRENT = ' aria-current="page"'


def page(file, title, desc, body):
    nav = "\n".join(f'        <li><a href="{f}"{CURRENT if f == file else ""}>{t}</a></li>' for f, t in PAGES)
    crumb = ('<li aria-current="page">Docs</li>' if file == "index.html"
             else f'<li><a href="index.html">Docs</a></li> <li aria-current="page">{title}</li>')
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{desc}">
  <title>{title} - RailTrack API Docs</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <a class="skip" href="#content">Skip to content</a>
  <header class="top">
    <a class="brand" href="index.html">RailTrack <span>API Docs</span></a>
    <p class="version">Version <data value="2.1">v2.1</data></p>
  </header>
  <div class="layout">
    <nav class="side" aria-label="Documentation">
      <ul>
{nav}
      </ul>
    </nav>
    <main id="content">
      <nav aria-label="Breadcrumb"><ol class="crumbs">{crumb}</ol></nav>
{body}
    </main>
  </div>
  <footer class="bottom">
    <p>RailTrack is a practice API created for a Web Programming practical.
       Last updated <time datetime="2026-09-28">28 September 2026</time>.</p>
    <address>Maintained by <a href="mailto:docs@railtrack.example">the RailTrack docs team</a></address>
  </footer>
</body>
</html>
"""


INDEX = """      <h1>RailTrack API</h1>
      <p class="lead">A <abbr title="Representational State Transfer">REST</abbr> API that returns train
        timetables, live running status and station details for Indian Railways routes in
        <abbr title="JavaScript Object Notation">JSON</abbr>.</p>
      <section aria-labelledby="what">
        <h2 id="what">What you can build</h2>
        <ul>
          <li>A station display board that shows the next arrivals.</li>
          <li>A trip planner that lists trains between two stations.</li>
          <li>A notifier that warns passengers when their train is late.</li>
        </ul>
      </section>
      <section aria-labelledby="terms">
        <h2 id="terms">Key terms</h2>
        <dl>
          <dt><dfn>Station code</dfn></dt><dd>A short unique code for a station, for example <code>CSMT</code> for Mumbai CSMT.</dd>
          <dt><dfn>Train number</dfn></dt><dd>The five-digit number of a train, for example <code>12127</code>.</dd>
          <dt><dfn>API key</dfn></dt><dd>A secret string that identifies your application in every request.</dd>
        </dl>
      </section>
      <aside class="note" aria-label="Note">
        <p><strong>Note:</strong> the free plan allows 100 requests per minute. See <a href="faq.html#limits">rate limits</a>.</p>
      </aside>"""

START = """      <h1>Getting Started</h1>
      <p class="lead">Make your first request in three steps.</p>
      <section aria-labelledby="steps">
        <h2 id="steps">Steps</h2>
        <ol>
          <li>Create an account and copy your <dfn>API key</dfn> from the dashboard.</li>
          <li>Send the key in the <code>X-Api-Key</code> header of every request.</li>
          <li>Call <code>GET /v2/trains/12127</code> and read the JSON response.</li>
        </ol>
      </section>
      <section aria-labelledby="example">
        <h2 id="example">Example request</h2>
        <figure>
          <pre><code>curl -H "X-Api-Key: YOUR_KEY" https://api.railtrack.example/v2/trains/12127</code></pre>
          <figcaption>Listing 1: Fetching the timetable of train 12127 with curl.</figcaption>
        </figure>
        <p>A successful call returns status <samp>200 OK</samp> and a body such as:</p>
        <figure>
          <pre><samp>{ "number": "12127", "name": "Mumbai - Pune Intercity Express",
  "from": "CSMT", "to": "PUNE", "departs": "06:40", "arrives": "09:57" }</samp></pre>
          <figcaption>Listing 2: Response body (shortened).</figcaption>
        </figure>
        <p>Tip: press <kbd>Ctrl</kbd> + <kbd>C</kbd> to copy the command from the listing.</p>
      </section>"""

ENDPOINTS = """      <h1>Endpoints</h1>
      <p class="lead">All paths start with <code>https://api.railtrack.example/v2</code>.</p>
      <section aria-labelledby="list">
        <h2 id="list">Endpoint reference</h2>
        <table>
          <caption>Table 1: Endpoints of RailTrack API v2</caption>
          <thead>
            <tr><th scope="col">Method</th><th scope="col">Path</th><th scope="col">Returns</th></tr>
          </thead>
          <tbody>
            <tr><th scope="row">GET</th><td><code>/trains/{number}</code></td><td>Timetable of one train</td></tr>
            <tr><th scope="row">GET</th><td><code>/trains/{number}/live</code></td><td>Current position and delay in minutes</td></tr>
            <tr><th scope="row">GET</th><td><code>/stations/{code}</code></td><td>Name, city and platforms of a station</td></tr>
            <tr><th scope="row">GET</th><td><code>/between?from=&amp;to=</code></td><td>Trains running between two stations</td></tr>
          </tbody>
        </table>
      </section>
      <section aria-labelledby="params">
        <h2 id="params">Query parameters of <code>/between</code></h2>
        <table>
          <caption>Table 2: Parameters</caption>
          <thead><tr><th scope="col">Name</th><th scope="col">Required</th><th scope="col">Example</th></tr></thead>
          <tbody>
            <tr><th scope="row"><code>from</code></th><td>Yes</td><td><code>CSMT</code></td></tr>
            <tr><th scope="row"><code>to</code></th><td>Yes</td><td><code>PUNE</code></td></tr>
            <tr><th scope="row"><code>date</code></th><td>No (today)</td><td><code>2026-10-02</code></td></tr>
          </tbody>
        </table>
      </section>"""

FAQ = """      <h1>Errors &amp; FAQ</h1>
      <p class="lead">What the status codes mean and answers to common questions.</p>
      <section aria-labelledby="codes">
        <h2 id="codes">Status codes</h2>
        <dl>
          <dt><code>400</code> Bad Request</dt><dd>A parameter is missing or has the wrong format.</dd>
          <dt><code>401</code> Unauthorized</dt><dd>The <code>X-Api-Key</code> header is missing or wrong.</dd>
          <dt><code>404</code> Not Found</dt><dd>No train or station with that number or code.</dd>
          <dt><code>429</code> Too Many Requests</dt><dd>You passed the rate limit; wait and retry.</dd>
        </dl>
      </section>
      <section aria-labelledby="questions">
        <h2 id="questions">Frequently asked questions</h2>
        <details open>
          <summary>How often is live status updated?</summary>
          <p>Every 60 seconds while the train is running.</p>
        </details>
        <details id="limits" open>
          <summary>What are the rate limits?</summary>
          <p>100 requests per minute on the free plan and 1000 on the college plan.</p>
        </details>
        <details>
          <summary>Are times in IST?</summary>
          <p>Yes, all times use Indian Standard Time (<abbr title="Coordinated Universal Time">UTC</abbr>+05:30).</p>
        </details>
      </section>"""

for file, title, desc, body in [
        ("index.html", "Overview", "RailTrack API overview: what the API offers and key terms.", INDEX),
        ("getting-started.html", "Getting Started", "Make your first RailTrack API request in three steps.", START),
        ("endpoints.html", "Endpoints", "Reference of all RailTrack API v2 endpoints and parameters.", ENDPOINTS),
        ("faq.html", "Errors and FAQ", "RailTrack API status codes and frequently asked questions.", FAQ)]:
    open(file, "w").write(page(file, title, desc, body))
