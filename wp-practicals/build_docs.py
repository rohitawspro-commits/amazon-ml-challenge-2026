"""Build the five Web Programming practical write-ups (Rohit Pujari, Roll No. 28) as .docx."""
import re
import sys

import pymupdf
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

NAME, ROLL = "Rohit Pujari", "28"
RUN_DIR = sys.argv[1] if len(sys.argv) > 1 else "."


def snip(path, start, end, nth=1, exact=False):
    lines = open(path).read().splitlines()
    i = next(k for k, l in enumerate(lines) if start in l)
    seen = 0
    for j in range(i, len(lines)):
        hit = lines[j].rstrip() == end if exact else end in lines[j]
        if hit and (j > i or not exact):
            seen += 1
            if seen == nth:
                block = lines[i:j + 1]
                pad = min(len(l) - len(l.lstrip()) for l in block if l.strip())
                return "\n".join(l[pad:] for l in block)
    raise ValueError(f"{end!r} not found in {path}")


def luminance(hex_):
    rgb = [int(hex_[k:k + 2], 16) / 255 for k in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return f"{(la + 0.05) / (lb + 0.05):.1f}:1"


# ---------------------------------------------------------------- document helpers
def new_doc():
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    st.font.size = Pt(11)
    st.paragraph_format.space_after = Pt(2)
    st.paragraph_format.line_spacing = 1.08
    s = doc.sections[0]
    s.page_height, s.page_width = Inches(11.69), Inches(8.27)
    s.top_margin = s.bottom_margin = Inches(0.7)
    s.left_margin = s.right_margin = Inches(0.8)
    fp = s.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run("Page ")
    r.font.size = Pt(9)
    r = fp.add_run()
    r.font.size = Pt(9)
    for tag, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if tag:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), tag)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        r._r.append(el)
    return doc


def P(doc, text="", size=11, bold=False, italic=False, align=WD_ALIGN_PARAGRAPH.JUSTIFY,
      before=0, after=2, underline=False):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(before), Pt(after)
    if text:
        add_rich(p, text, size, bold, italic, underline)
    return p


def add_rich(p, text, size=11, bold=False, italic=False, underline=False):
    """**bold** segments inside text."""
    for k, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        if part:
            r = p.add_run(part)
            r.font.size, r.bold, r.italic, r.underline = Pt(size), bold or k % 2 == 1, italic, underline


def section(doc, text):
    P(doc, text, size=13, bold=True, underline=True, align=WD_ALIGN_PARAGRAPH.LEFT, before=6,
      after=2).paragraph_format.keep_with_next = True


def sub(doc, text):
    P(doc, text, size=11.5, bold=True, align=WD_ALIGN_PARAGRAPH.LEFT, before=4,
      after=1).paragraph_format.keep_with_next = True


def bullets(doc, items):
    for it in items:
        p = P(doc, after=1)
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.first_line_indent = Inches(-0.18)
        add_rich(p, "•  " + it)


def table(doc, rows, widths=None):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    t.autofit = False
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.cell(i, j)
            if widths:
                c.width = Inches(widths[j])
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(val)
            r.font.size, r.bold = Pt(9.5), i == 0
    if widths:
        for j, w in enumerate(widths):
            t.columns[j].width = Inches(w)
    P(doc, after=2)


def code(doc, label, text):
    P(doc, label, size=11, bold=True, align=WD_ALIGN_PARAGRAPH.LEFT, before=3,
      after=1).paragraph_format.keep_with_next = True
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.0
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), "F3F3F3")
    p._p.get_or_add_pPr().append(shd)
    for k, line in enumerate(text.split("\n")):
        r = p.add_run(line)
        r.font.name, r.font.size = "Courier New", Pt(8.5)
        r._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "Courier New")
        if k < len(text.split("\n")) - 1:
            r.add_break()


def figure(doc, img, caption, max_h=3.7, max_w=6.4):
    pix = pymupdf.Pixmap(img)
    w = max_w
    if w * pix.height / pix.width > max_h:
        w = max_h * pix.width / pix.height
    p = P(doc, align=WD_ALIGN_PARAGRAPH.CENTER, before=4, after=1)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(img, width=Inches(w))
    P(doc, caption, size=10, align=WD_ALIGN_PARAGRAPH.CENTER, after=6)


def write(doc, exp):
    P(doc, f"EXPERIMENT NO. {exp['no']}", size=15, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
    P(doc, exp["title"], size=13, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
    P(doc, f"Name: {NAME}          Roll No.: {ROLL}          Date: ____________", size=11,
      align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
    section(doc, "Aim:")
    P(doc, exp["aim"])
    section(doc, "Theory:")
    for kind, *val in exp["theory"]:
        {"p": lambda v: P(doc, v[0]), "h": lambda v: sub(doc, v[0]), "b": lambda v: bullets(doc, v[0]),
         "t": lambda v: table(doc, v[0], v[1] if len(v) > 1 else None)}[kind](val)
    section(doc, "Important Code:")
    for label, text in exp["code"]:
        code(doc, label, text)
    section(doc, "Output:")
    for img, cap in exp["figures"]:
        figure(doc, img, cap)
    section(doc, "Conclusion:")
    P(doc, exp["conclusion"])


def build(exp):
    doc = new_doc()
    write(doc, exp)
    out = f"WP_Practicals_Rohit_Pujari_28_Exp{exp['no']:02d}.docx"
    doc.save(out)
    return out


def build_combined(exps):
    doc = new_doc()
    for k, exp in enumerate(exps):
        if k:
            doc.add_page_break()
        write(doc, exp)
    doc.save("WP_Practicals_Rohit_Pujari_28.docx")
    return "WP_Practicals_Rohit_Pujari_28.docx"


# ---------------------------------------------------------------- Experiment 1
EXP01 = {
    "no": 1,
    "title": "Develop a semantic, multi-page technical documentation site",
    "aim": "To develop the documentation website of \u201cRailTrack\u201d, a practice REST API for Indian Railways "
           "timetables, as four linked pages (Overview, Getting Started, Endpoints and Errors & FAQ) written in "
           "semantic HTML5 with landmarks, breadcrumbs, a skip link, accessible data tables, definition lists and "
           "disclosure widgets, and to check every page automatically with a script that tests the heading "
           "outline, the landmarks, the table headers and all internal links.",
    "theory": [
        ("p", "Semantic HTML means choosing each element for what the content is, not for how it should look. A "
              "<div> or <span> says nothing about its content, while <nav>, <main>, <table> or <dl> tell the "
              "browser that the content is a menu, the main part of the page, tabular data or a list of terms. "
              "Browsers build an accessibility tree from these meanings, which screen readers use to jump between "
              "regions and headings; search engines and reader modes use the same information. The look is added "
              "separately with CSS, so the markup stays clean and easy to maintain."),
        ("h", "Page structure and landmarks"),
        ("t", [["Element", "Use in the RailTrack docs"],
               ["<header>", "Site banner with the logo link and the API version written as <data value=\"2.1\">"],
               ["<nav aria-label=\"Documentation\">", "Side menu of the four pages; the current page has aria-current=\"page\""],
               ["<nav aria-label=\"Breadcrumb\">", "An ordered list (Docs / Endpoints) showing where the page is; the two "
                                                   "<nav> elements are told apart by their aria-label"],
               ["<main id=\"content\">", "The one main region of each page; target of the skip link"],
               ["<section aria-labelledby>", "Each section is named by the id of its own <h2>"],
               ["<aside>", "A side note about rate limits that is related to, but not part of, the main text"],
               ["<footer>, <address>, <time>", "Contact of the maintainers and a machine-readable update date"]],
         [2.2, 4.3]),
        ("h", "Content elements chosen for documentation"),
        ("b", ["**<dl>, <dt>, <dd> and <dfn>:** name-value pairs such as the key terms and the status codes; <dfn> "
               "marks the place where a term is defined.",
               "**<ol> versus <ul>:** the setup steps use an ordered list because the order matters; the list of "
               "possible applications uses an unordered list.",
               "**<figure>, <pre>, <code>, <samp>, <kbd>:** code listings are figures with a <figcaption>; <code> is "
               "code to type, <samp> is output from the program and <kbd> is a key on the keyboard.",
               "**<abbr title>:** gives the full form of REST, JSON and UTC when the pointer rests on the word.",
               "**<details> and <summary>:** each FAQ answer is a native disclosure widget that opens with mouse or "
               "keyboard without any JavaScript. The link faq.html#limits opens the page at the matching answer."]),
        ("h", "Accessible data tables"),
        ("p", "The endpoint table has a <caption>, column headers in <thead> with scope=\"col\" and the first cell of "
              "each row written as <th scope=\"row\">. A screen reader can then announce every cell together with its "
              "row and column header, for example \u201cGET, Path, /trains/{number}\u201d."),
        ("h", "Headings, skip link and metadata"),
        ("p", "Every page has exactly one <h1>, <h2> for its sections and no skipped levels, so the heading outline is "
              "a correct table of contents. A \u201cSkip to content\u201d link is the first focusable element; it is "
              "moved off-screen with CSS and appears when it receives keyboard focus. Each page has lang=\"en\", its own "
              "<title> and a meta description for search results."),
        ("h", "Consistent pages and automatic checks"),
        ("p", "The small script make_pages.py writes the four pages from one layout function, so the header, menu and "
              "footer are identical everywhere and aria-current is set on the correct menu item automatically. The "
              "script check.js opens every page in Chromium through Playwright and tests the rules below."),
        ("t", [["Check", "Rule"],
               ["Language and metadata", "lang=\"en\" and a meta description are present"],
               ["Headings", "Exactly one <h1>; no level is skipped (for example <h2> followed by <h4>)"],
               ["Landmarks", "<header>, <nav>, <main> and <footer> all exist; the side menu has aria-current"],
               ["Sections and tables", "Every <section> has aria-labelledby; every <th> has a scope"],
               ["Links", "Every internal link points to an existing page and, with #id, to an existing id"]],
         [2.0, 4.5]),
        ("p", "Result of node check.js: all four pages passed, with 7 internal links per page and no broken link."),
    ],
    "code": [
        ("HTML - page skeleton (index.html)", snip("exp01/index.html", "<body>", "<main id=\"content\">")),
        ("HTML - accessible table (endpoints.html)",
         snip("exp01/endpoints.html", "<table>", "<tr><th scope=\"row\">GET</th><td><code>/trains/{number}</code>")
         + "\n    ...\n  </tbody>\n</table>"),
        ("HTML - FAQ entry and CSS for the current page",
         snip("exp01/faq.html", "<details id=\"limits\"", "</details>") + "\n\n"
         + snip("exp01/style.css", ".side a[aria-current", ".side a[aria-current") + "\n"
         + snip("exp01/style.css", ".skip {", ".skip:focus")),
    ],
    "figures": [("shots/exp01_1.png", "Figure 1.1: Overview page - side menu with aria-current, breadcrumb, <abbr>, "
                                      "<dl> with <dfn> and an <aside> note"),
                ("shots/exp01_2.png", "Figure 1.2: Endpoints page - tables with <caption>, column headers and row "
                                      "headers (th scope=\"row\")")],
    "conclusion": "A four-page technical documentation site was developed in semantic HTML5. Landmarks, breadcrumbs, a "
                  "skip link and a correct heading outline made the pages easy to navigate, while definition lists, "
                  "figures, accessible tables and <details> widgets gave each kind of content its proper meaning. The "
                  "automatic check script confirmed that all four pages follow these rules and have no broken links.",
}

# ---------------------------------------------------------------- Experiment 4
EXP04 = {
    "no": 4,
    "title": "Implement a dark/light mode toggle using CSS Custom Properties (Variables)",
    "aim": "To build “RecipeBox”, a recipe listing page whose complete colour scheme is stored in CSS "
           "custom properties with two sets of values selected by a data-theme attribute on the <html> "
           "element; to provide a three-way Light / Dark / System switch that can follow the operating-system "
           "setting through matchMedia(), to remember the user's choice in localStorage and to apply the saved "
           "theme before the first paint so that the page never flashes in the wrong colours.",
    "theory": [
        ("p", "CSS custom properties (CSS variables) are properties whose names begin with two hyphens, for "
              "example --accent. They are declared like any other property, read with the var() function, "
              "inherited by child elements and follow the normal cascade, so a more specific rule can give them "
              "a new value. Unlike variables of a pre-processor such as Sass, they exist while the page is "
              "running, so when their value changes the browser immediately re-styles every element that uses them."),
        ("h", "Two variable sets selected by one attribute"),
        ("p", "RecipeBox declares all its design tokens once on :root. A second rule, :root[data-theme=\"dark\"], "
              "has a higher specificity because of the attribute selector and redefines only the colour tokens. "
              "No component rule contains a colour code; the header, cards and tags only use var(--surface), "
              "var(--text), var(--accent) and so on. Switching the theme therefore means changing a single "
              "attribute: document.documentElement.dataset.theme = 'dark'."),
        ("t", [["Token", "Light theme", "Dark theme", "Used for"],
               ["--bg", "#fbf7f1", "#15120f", "Page background"],
               ["--surface", "#ffffff", "#211c17", "Header bar and recipe cards"],
               ["--text", "#2b2118", "#f2ebe3", "Recipe names and body text"],
               ["--muted", "#7a6a5c", "#b0a193", "Cooking time and status line"],
               ["--accent", "#b4450c", "#fb923c", "Logo, selected button, tag text"],
               ["--border", "#e8dccd", "#3a3129", "Card and header borders"],
               ["--shadow", "soft shadow", "none", "Card elevation (shadows are hard to see on dark)"]],
         [1.0, 1.1, 1.1, 3.3]),
        ("p", "Tokens that do not depend on the theme, such as --radius and --gap, are written only once and are "
              "shared by both themes. The colour pairs were chosen for readability: body text on the background "
              f"has a contrast ratio of {contrast('#2b2118', '#fbf7f1')} in the light theme and "
              f"{contrast('#f2ebe3', '#15120f')} in the dark theme, far above the WCAG AA minimum of 4.5:1."),
        ("h", "Three modes: Light, Dark and System"),
        ("b", ["**Mode and theme are different:** the mode is what the user selected (light, dark or system) and "
               "is stored in localStorage; the theme is what is actually applied (light or dark).",
               "**System mode:** window.matchMedia('(prefers-color-scheme: dark)') returns a MediaQueryList whose "
               ".matches property tells whether the operating system is in dark mode.",
               "**Live OS changes:** the MediaQueryList fires a change event when the user changes the OS setting "
               "while the page is open. RecipeBox re-renders only if the saved mode is still “system”, so an "
               "explicit Light or Dark choice is never overridden.",
               "**Accessibility:** the three buttons are inside role=\"group\" with an aria-label, and each button's "
               "aria-pressed attribute tells screen readers which mode is selected."]),
        ("h", "Avoiding the flash of the wrong theme"),
        ("p", "If the theme were applied by a script at the end of <body>, the browser could paint the light page "
              "first and switch a moment later. RecipeBox therefore places a very small inline script inside "
              "<head> that reads localStorage and sets data-theme before the body is parsed. The tag <meta "
              "name=\"color-scheme\" content=\"light dark\"> tells the browser that both schemes are supported, so "
              "scrollbars and form controls are also drawn in the matching style. All localStorage calls are "
              "wrapped in try...catch because storage can be blocked, in which case the page falls back to System."),
        ("h", "Reading a variable back"),
        ("p", "getComputedStyle(document.documentElement).getPropertyValue('--accent') returns the value that is "
              "currently in effect. The status line at the bottom of the page prints the mode, the applied theme "
              "and this value, which proves that the same variable name resolves to a different colour in each theme."),
        ("h", "Testing the toggle"),
        ("t", [["Test", "Expected result", "Observed"],
               ["First visit, OS in light mode", "Mode System, light theme applied", "As expected"],
               ["Click “Dark”", "data-theme=\"dark\", Dark button pressed", "As expected"],
               ["Reload after choosing Dark", "Saved mode read in <head>, page opens dark", "As expected"],
               ["System selected, OS switched to dark", "change event switches page to dark", "As expected (Fig. 4.2)"],
               ["Dark selected, OS switched to light", "Page stays dark (explicit choice wins)", "As expected"]],
         [2.2, 3.0, 1.3]),
    ],
    "code": [
        ("CSS - design tokens and the dark variable set", snip("exp04/index.html", ":root {", "  }", 2, exact=True)),
        ("HTML <head> - apply the saved theme before the first paint", snip("exp04/index.html", "<script>", "</script>")),
        ("JavaScript - switch, save and follow the OS setting",
         snip("exp04/index.html", "function readMode()", "render(readMode());")),
    ],
    "figures": [("shots/exp04_1.png", "Figure 4.1: RecipeBox with “Light” selected (applied theme light, --accent = #b4450c)"),
                ("shots/exp04_2.png", "Figure 4.2: “System” selected while the operating system is in dark mode "
                                      "(applied theme dark, --accent = #fb923c)")],
    "conclusion": "A recipe page was themed entirely with CSS custom properties, where a single data-theme attribute "
                  "on the root element selects the dark set of values. The three-way switch supported Light, Dark and "
                  "System modes, matchMedia() and its change event followed the operating-system preference, "
                  "localStorage remembered the choice and an inline script in <head> applied it before the first paint.",
}

# ---------------------------------------------------------------- Experiment 5
EXP05 = {
    "no": 5,
    "title": "Build a real-time search filter for a list of items using JavaScript strings/arrays",
    "aim": "To build “BookShelf”, a college library catalogue of 20 books that is filtered on every "
           "keystroke by title and author, where a query of several words must match all the words in any order; "
           "genre chips generated from the data narrow the list, the result can be sorted by title, year or rating, "
           "the matched words are highlighted, and the current search is kept in the page URL so that it can be "
           "bookmarked or shared.",
    "theory": [
        ("p", "The catalogue is a JavaScript array of objects, each with title, author, genre, year and rating. The "
              "search box listens to the input event, which fires after every character that is typed, pasted or "
              "deleted. On each event the program builds a new array with a chain of array methods and redraws the "
              "list. The original array is never modified: slice() makes a copy before sort(), because sort() "
              "changes the array it is called on."),
        ("h", "Multi-word matching with split() and every()"),
        ("p", "The query is converted to lower case and split on white space with split(/\\s+/); filter(Boolean) "
              "removes the empty strings produced by extra spaces. For each book the title and author are joined "
              "into one lower-case string, and every(word => text.includes(word)) is true only if all the words "
              "occur in it. Therefore “rowling harry” finds both Harry Potter books although the words are "
              "in a different order from the title. For an empty query the word list is empty, and every() on an "
              "empty array returns true, so all books are shown without any special case."),
        ("t", [["Method", "Purpose in BookShelf", "Example"],
               ["split(/\\s+/)", "Break the query into words", "\"rowling  harry\" -> [\"rowling\", \"harry\"]"],
               ["filter(Boolean)", "Drop empty strings", "[\"\", \"code\"] -> [\"code\"]"],
               ["every(fn)", "All words must be present", "true for 2 of the 20 books"],
               ["includes(s)", "Substring test", "\"clean code robert c. martin\".includes(\"code\")"],
               ["[...new Set(arr)]", "Unique genres for the chips", "20 books -> 7 genres"],
               ["reduce(fn, 0)", "Average rating of the results", "(4.5 + 4.4) / 2 = 4.45"],
               ["localeCompare()", "Alphabetical sort", "\"Ikigai\" before \"Sapiens\""],
               ["replace(re, \"<mark>$1</mark>\")", "Highlight matched words", "Harry -> <mark>Harry</mark>"]],
         [1.8, 2.0, 2.7]),
        ("h", "Genre chips and sorting"),
        ("p", "The chips are not written in the HTML; they are generated from the data with new Set(), so adding a "
              "book of a new genre automatically adds a chip, and the count on each chip is found with "
              "filter().length. Instead of one listener per chip, a single click listener on the chip container "
              "reads event.target.dataset.genre (event delegation). The sort order comes from an object of "
              "comparator functions: title uses localeCompare(), year uses b.year - a.year for newest first, and "
              "rating sorts by rating and breaks ties by title."),
        ("h", "Safe highlighting with regular expressions"),
        ("p", "The matched words are wrapped in <mark> using one regular expression built from all query words, "
              "with the flags g (all matches) and i (ignore case); the capture group $1 keeps the original "
              "capitalisation. Because the words come from the user, characters such as + ( ) . * that have a "
              "special meaning in a RegExp are first escaped with a backslash, so a query such as “c++ (x” "
              "cannot throw an error. The book text is HTML-escaped before the <mark> tags are inserted."),
        ("h", "Keeping the search in the URL"),
        ("b", ["**URLSearchParams** builds a query string such as ?q=code&genre=Programming&sort=rating from the "
               "current state and reads it back when the page loads.",
               "**history.replaceState()** updates the address bar without reloading the page and without adding "
               "one history entry per keystroke, so the Back button still leaves the page.",
               "**Keyboard shortcuts:** “/” focuses the search box and Esc clears it."]),
        ("h", "Testing the filter"),
        ("t", [["Test", "Expected result", "Observed"],
               ["Type \"rowling harry\"", "2 of 20 books, words highlighted", "As expected (Fig. 5.1)"],
               ["Open ?q=code&genre=Programming", "State restored from URL, 1 book (Clean Code)", "As expected"],
               ["Type \"xyz\"", "Message \"No books match ...\"", "As expected"],
               ["Type \"c++ (x\"", "No error, 0 results", "As expected"],
               ["Press Esc, choose All", "All 20 books shown", "As expected"]],
         [2.2, 3.0, 1.3]),
    ],
    "code": [
        ("JavaScript - escaping and highlighting", snip("exp05/index.html", "const escapeRegex", "  }", exact=True)),
        ("JavaScript - filtering, sorting and the URL", snip("exp05/index.html", "function render()", ".slice().sort(sorters[state.sort]);")
         + "\n  // ... list and chips are rendered here ...\n"
         + snip("exp05/index.html", "const p = new URLSearchParams();", "history.replaceState")),
        ("JavaScript - events", snip("exp05/index.html", "$('q').addEventListener('input'", "  });", exact=True)),
    ],
    "figures": [("shots/exp05_1.png", "Figure 5.1: Query “harry rowling” - 2 of 20 books match both words, "
                                      "matched words highlighted"),
                ("shots/exp05_2.png", "Figure 5.2: Genre chip “Programming” with the sort order “Top rated”")],
    "conclusion": "A real-time book search was built using only JavaScript string and array methods. split() and "
                  "every() allowed multi-word queries in any order, filter(), sort() and reduce() produced the result "
                  "list and its average rating, a Set generated the genre chips, an escaped regular expression "
                  "highlighted matches safely, and URLSearchParams with history.replaceState() kept the search in "
                  "the URL.",
}

# ---------------------------------------------------------------- Experiment 8
EXP08 = {
    "no": 8,
    "title": "Implement custom middleware for user authorization in an Express app",
    "aim": "To secure “CampusLibrary”, a library REST API built with Express on port 3008, using only "
           "hand-written middleware: a request logger, a signed-token authentication middleware (HMAC-SHA256, "
           "without any authentication library), a login-required check, a role-based authorize(...roles) "
           "factory, an owner-or-staff check for loan records, a rate limiter on the login route, and central "
           "404 and error handlers.",
    "theory": [
        ("p", "In Express a middleware is a function (req, res, next). It can read or change the request, end the "
              "request by sending a response, or call next() to hand control to the next function. Middleware "
              "registered with app.use() runs for every request in the order it was added; middleware passed as "
              "extra arguments to a route runs only for that route, from left to right, before the final handler. "
              "An error handler is recognised by its four parameters (err, req, res, next)."),
        ("h", "Signed tokens instead of server-side sessions"),
        ("p", "After a successful login the server returns a token made of two parts: base64url(payload) + \".\" + "
              "base64url(HMAC-SHA256(payload, secret)). The payload contains the user id, the role and an expiry "
              "time 15 minutes ahead. The client sends it back in the header Authorization: Bearer <token>. The "
              "server recomputes the HMAC with its secret; if even one character of the payload was changed (for "
              "example the role “student” replaced by “admin”), the signature no longer matches and "
              "the request is rejected. This is the same idea as a JSON Web Token, written by hand."),
        ("b", ["**Stateless:** the server keeps nothing per login, so any number of server instances can check a "
               "token. The drawback is that a token cannot be cancelled before it expires, which is why the "
               "lifetime is short.",
               "**Encoded, not encrypted:** anyone can read the payload, so it holds no password or secret data.",
               "**Password storage:** passwords are never stored; crypto.scryptSync() stores a salted hash.",
               "**Timing-safe comparison:** crypto.timingSafeEqual() compares signatures in constant time, so an "
               "attacker cannot guess a signature byte by byte from response times."]),
        ("h", "The middleware chain"),
        ("t", [["Middleware", "Registered", "Responsibility", "On failure"],
               ["requestLogger", "app.use (global)", "Gives each request an id; logs method, URL, status, user and time on the finish event", "-"],
               ["express.json()", "app.use (global)", "Parses the JSON body into req.body", "400 Invalid JSON body"],
               ["authenticate", "app.use (global)", "If a Bearer token is present, verifies it and sets req.user; guests pass through", "401 Invalid token"],
               ["requireLogin", "per route", "req.user must exist", "401 Login required"],
               ["authorize(...roles)", "per route", "req.user.role must be in the list", "403 Forbidden"],
               ["selfOr(...roles)", "/api/loans/:userId", "Own user id, or a staff role", "403 Forbidden"],
               ["rateLimit(5, 60000)", "/api/login", "At most 5 login attempts per IP per minute", "429 Too many"],
               ["404 and error handler", "last", "Unknown route / unexpected exception", "404 / 500"]],
         [1.35, 1.2, 2.75, 1.2]),
        ("h", "Authentication, authorization and status codes"),
        ("p", "Authentication answers “who are you?” (token check) and authorization answers “what may you "
              "do?” (role and ownership). authorize() and selfOr() are factory functions: calling "
              "authorize('librarian', 'admin') returns a new middleware that remembers the allowed roles through a "
              "closure. The API uses 401 when the caller is not logged in or the token is invalid, 403 when the "
              "caller is known but not allowed, 404 for a missing book or route and 429 for too many login attempts."),
        ("t", [["Route", "Guest", "Student", "Librarian", "Admin"],
               ["GET /api/books", "Yes", "Yes", "Yes", "Yes"],
               ["GET /api/me", "401", "Yes", "Yes", "Yes"],
               ["GET /api/loans/:userId", "401", "Own only", "Any user", "Any user"],
               ["POST /api/books", "401", "403", "Yes", "Yes"],
               ["DELETE /api/books/:id", "401", "403", "403", "Yes"]],
         [2.1, 0.9, 1.1, 1.2, 1.2]),
        ("p", "A test script (test.js) calls every route with fetch() as a guest, a student, the librarian and "
              "the admin, and also sends a wrong password and a tampered token. Its output is shown in Figure 8.1 "
              "and the matching server log in Figure 8.2."),
    ],
    "code": [
        ("Signing and verifying a token", snip("exp08/server.js", "const b64 =", "}", 2, exact=True)),
        ("Authentication and authorization middleware",
         snip("exp08/server.js", "function authenticate", "You can only view your own loans")),
        ("Routes - middleware composed per route", snip("exp08/server.js", "app.get('/api/books'", "app.post('/api/books'")
         + " ... })\n" + snip("exp08/server.js", "app.delete('/api/books/:id'", "app.delete('/api/books/:id'") + " ... })"),
    ],
    "figures": [("shots/exp08_1.png", "Figure 8.1: Output of test.js - 200, 201, 401 and 403 responses for guest, student, "
                                      "librarian and admin requests"),
                ("shots/exp08_2.png", "Figure 8.2: Server console written by the requestLogger middleware "
                                      "(request id, status, user and role, time)")],
    "conclusion": "The CampusLibrary API was protected with custom Express middleware only. A hand-written HMAC-signed "
                  "token identified the user without server-side sessions, authorize() and selfOr() enforced role and "
                  "ownership rules, and the logger, rate limiter and error handlers completed the chain. The test "
                  "script confirmed the correct 200, 201, 401 and 403 responses, and a tampered token was rejected.",
}

# ---------------------------------------------------------------- Experiment 9
seed_line = open(f"{RUN_DIR}/exp09_seed.txt").readline().strip()
EXP09 = {
    "no": 9,
    "title": "Design a blog database and write scripts to seed it with mock data",
    "aim": "To design the SQLite database of “CodeJournal”, a developer blog with authors, posts, tags and "
           "threaded comments (replies to comments); to enforce data rules with constraints, speed up frequent "
           "queries with indexes and provide a statistics view; and to write a Node.js seed script (options "
           "--posts and --seed, a single transaction with rollback) and a query script that uses joins, "
           "aggregation and a recursive CTE, using Node.js's built-in node:sqlite module.",
    "theory": [
        ("p", "Designing a database starts with the entities and their relationships. In CodeJournal an author "
              "writes many posts (one-to-many), a post has many tags and a tag belongs to many posts "
              "(many-to-many, stored in the junction table post_tags), and a post has many comments (one-to-many). "
              "A comment can also answer another comment, which is a one-to-many relationship of the comments "
              "table with itself (a self-referencing foreign key)."),
        ("h", "Tables"),
        ("t", [["Table", "Important columns", "Constraints and purpose"],
               ["authors", "id, username, full_name, email, joined_on", "username and email UNIQUE; CHECK on the e-mail pattern"],
               ["posts", "id, author_id FK, title, slug, body, status, views, published_at",
                "slug UNIQUE (used in the URL); status IN ('draft', 'published'); views >= 0; a published post must have a date"],
               ["tags", "id, name", "name UNIQUE COLLATE NOCASE, so \"SQL\" and \"sql\" are the same tag"],
               ["post_tags", "post_id FK, tag_id FK", "Composite PRIMARY KEY (post_id, tag_id); junction table"],
               ["comments", "id, post_id FK, parent_id FK, name, body, created_at",
                "parent_id NULL for a top-level comment, otherwise the id of the comment being answered"]],
         [0.95, 2.45, 3.1]),
        ("h", "Integrity rules"),
        ("b", ["**PRAGMA foreign_keys = ON:** SQLite checks foreign keys only when this is switched on.",
               "**ON DELETE CASCADE:** deleting a post removes its tag links and comments; deleting a comment "
               "removes its replies.",
               "**Table-level CHECK:** CHECK (status = 'draft' OR published_at IS NOT NULL) compares two columns of "
               "the same row, which a column constraint cannot do.",
               "**Normal form:** author names and tag names are stored once and referenced by id, so the design is in "
               "third normal form. Dates are ISO text (YYYY-MM-DD), which sorts correctly as text."]),
        ("h", "Indexes and the view"),
        ("p", "SQLite automatically indexes primary keys and UNIQUE columns but not foreign keys, so indexes are added "
              "on posts(author_id), comments(post_id) and post_tags(tag_id), plus a composite index on "
              "posts(status, published_at) for “latest published posts”. EXPLAIN QUERY PLAN confirms that "
              "a search by author uses idx_posts_author instead of scanning the table (bottom of Figure 9.2). The "
              "view v_post_stats joins posts with authors and uses correlated sub-queries and GROUP_CONCAT() to "
              "return the comment count and tag list of every post, so programs can query it like a table."),
        ("h", "Seeding strategy"),
        ("b", ["**Options:** --posts N and --seed S are read from process.argv; the file is deleted and re-created "
               "from schema.sql on every run.",
               "**Reproducible data:** a small seeded random generator (mulberry32) is used instead of Math.random(), "
               "so the same --seed always creates exactly the same rows.",
               "**Realistic rules:** about 80% of posts are published; drafts have no date and 0 views, which "
               "satisfies the CHECK constraint. Only published posts get comments, and about 40% of comments get a "
               "reply from the author.",
               "**Prepared statements** are created once and reused for every row, which is faster and safe from SQL "
               "injection. INSERT OR IGNORE skips a tag that was already chosen for the same post.",
               f"**One transaction:** all inserts run between BEGIN and COMMIT; on any error ROLLBACK leaves the "
               f"database empty instead of half-filled. Result: “{seed_line}” (Figure 9.1)."]),
        ("h", "Queries"),
        ("t", [["Query", "SQL features", "Result"],
               ["1. Posts and views per author", "LEFT JOIN with the condition in ON, GROUP BY, SUM()", "Every author listed, busiest first"],
               ["2. Most used tags", "JOIN, GROUP BY, ORDER BY, LIMIT", "Top five tags"],
               ["3. Top posts", "SELECT from the view v_post_stats", "Title, views, comments, tags"],
               ["4. Comment thread", "WITH RECURSIVE, depth and sort path", "Each reply printed under its parent"]],
         [1.9, 2.7, 1.9]),
    ],
    "code": [
        ("schema.sql - posts, threaded comments and the view",
         snip("exp09/schema.sql", "CREATE TABLE posts", ");", exact=True) + "\n\n"
         + snip("exp09/schema.sql", "CREATE TABLE comments", ");", exact=True) + "\n\n"
         + snip("exp09/schema.sql", "CREATE VIEW", "FROM posts p JOIN")),
        ("seed.js - seeded random numbers and one transaction",
         snip("exp09/seed.js", "let s = Number", "return ((t ^") + "\n\n"
         + snip("exp09/seed.js", "db.exec('BEGIN');", "try {")
         + "\n  // ... insert authors, tags, posts, post_tags and comments with prepared statements ...\n"
         + snip("exp09/seed.js", "  db.exec('COMMIT');", "}", exact=True)),
        ("queries.js - recursive CTE for the comment thread", snip("exp09/queries.js", "WITH RECURSIVE", "ORDER BY sort_path")),
    ],
    "figures": [("shots/exp09_1.png", "Figure 9.1: Seeding with --posts 40 --seed 7 (row counts) and query 1"),
                ("shots/exp09_2.png", "Figure 9.2: Queries 2-4 (tags, the view, the recursive comment thread) and the query plan")],
    "conclusion": "A normalised SQLite database for a developer blog was designed with foreign keys, CHECK constraints, a "
                  "junction table for tags and a self-referencing comments table for replies. Indexes and a view "
                  "supported the common queries. The seed script generated reproducible mock data inside a single "
                  "transaction, and the query script demonstrated joins, aggregation, the view and a recursive CTE.",
}

# ---------------------------------------------------------------- Experiment 11
EXP11 = {
    "no": 11,
    "title": "Develop a Single Page Application (SPA) dashboard that polls a REST API",
    "aim": "To develop “ServerPulse”, a single page monitoring dashboard served by Express on port 3011 that "
           "polls the REST endpoints /api/servers and /api/servers/:id, shows the CPU and memory usage of six "
           "simulated servers with health badges, opens a detail view with a canvas line chart of CPU history "
           "through hash routing, and makes polling robust with AbortController time-outs, exponential back-off "
           "on errors, a Pause button and automatic pausing when the browser tab is hidden.",
    "theory": [
        ("p", "A Single Page Application loads one HTML page and then updates only parts of it with JavaScript, "
              "using JSON data fetched from a REST API. Moving between views does not reload the page. HTTP is a "
              "request-response protocol, so the server cannot push new values to the page by itself; the "
              "simplest way to keep the dashboard current is polling, i.e. asking the server again at regular "
              "intervals. (WebSockets and Server-Sent Events can push data, but need extra server support.)"),
        ("h", "REST endpoints and simulated data"),
        ("t", [["Method and path", "Response", "Used by"],
               ["GET /api/servers", "{ time, servers: [{ id, name, region, cpu, mem, status }] }", "Overview, every poll"],
               ["GET /api/servers/:id", "One server plus history (last 30 CPU readings); 404 for unknown id", "Detail view"],
               ["GET /", "index.html, app.js and style.css via express.static", "First page load"]],
         [1.6, 3.4, 1.5]),
        ("p", "On the server, setInterval() produces a new reading every 2 seconds. CPU follows a random walk around "
              "a base value for each server, and worker-01 is deliberately unreliable and is reported as down about "
              "half of the time. The status is calculated from the numbers: down, critical (CPU above 85% or memory "
              "above 90%), warning (CPU above 70%) or healthy."),
        ("h", "The polling loop"),
        ("b", ["**Recursive setTimeout():** the next poll is scheduled only after the previous response has been "
               "handled, so slow responses never overlap, and the delay can change after every poll. setInterval() "
               "would fire at a fixed rate regardless.",
               "**AbortController:** each request gets a signal; a 5-second timer aborts a request that hangs, and a "
               "new poll (for example after a view change) aborts the one still running.",
               "**Exponential back-off:** after a failure the delay doubles (3, 6, 12, 24, then at most 30 s) and a "
               "red banner shows the retry time; after the next success it returns to 3 s. This avoids flooding a "
               "server that is already in trouble.",
               "**Page Visibility API:** when document.hidden becomes true (tab in the background) the "
               "visibilitychange event stops polling; it restarts immediately when the tab becomes visible.",
               "**cache: 'no-store'** makes sure the browser never answers a poll from its HTTP cache."]),
        ("t", [["Situation", "Next poll"],
               ["Successful response", "after 3 s"],
               ["Network error, HTTP error or 5 s timeout", "previous delay x 2, maximum 30 s"],
               ["Pause button pressed", "none until Resume"],
               ["Tab hidden", "none until the tab is visible again"],
               ["Hash changed (another view)", "immediately"]],
         [3.4, 3.1]),
        ("h", "Hash routing and rendering"),
        ("p", "The views are chosen from location.hash: \"#/server/5\".split('/') gives [\"#\", \"server\", \"5\"], "
              "so the router knows which endpoint to call. A hashchange event starts a new poll at once. The part "
              "after # is never sent to the server, so no extra server routes are needed, the Back button works and "
              "each view can be bookmarked. Cards are built with template literals, reduce() counts servers per "
              "status for the summary row, and the width of each usage bar is animated with a CSS transition. The "
              "detail view draws the CPU history on a <canvas> with the 2D context: grid lines at 0, 50 and 100%, "
              "then moveTo()/lineTo() for each reading, scaled to the height of the canvas."),
    ],
    "code": [
        ("app.js - router and polling with back-off",
         snip("exp11/public/app.js", "function route()", "}", exact=True) + "\n\n"
         + snip("exp11/public/app.js", "async function poll()", "}", 2, exact=True)),
        ("app.js - pause when the tab is hidden",
         snip("exp11/public/app.js", "document.addEventListener('visibilitychange'", "});", exact=True)),
        ("server.js - REST endpoints", snip("exp11/server.js", "app.get('/api/servers',", "});", exact=True)),
    ],
    "figures": [("shots/exp11_1.png", "Figure 11.1: Overview view (#/) - live CPU and memory of six servers with the status summary"),
                ("shots/exp11_2.png", "Figure 11.2: Detail view (#/server/5) - CPU history of cache-01 drawn on a canvas")],
    "conclusion": "A single page monitoring dashboard was developed that polls an Express REST API. Hash routing switched "
                  "between the overview and detail views without page reloads, and the canvas chart showed the CPU "
                  "history. Recursive setTimeout(), AbortController time-outs, exponential back-off and the Page "
                  "Visibility API made the polling efficient and robust.",
}

if __name__ == "__main__":
    ALL = (EXP01, EXP04, EXP05, EXP08, EXP09, EXP11)
    for e in ALL:
        print(build(e))
    print(build_combined(ALL))
