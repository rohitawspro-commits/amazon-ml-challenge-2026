"""Country-agnostic normalisation of business names and addresses.

Everything here is deterministic string processing driven only by the record itself
(no external lookups). Per-country tables (state abbreviations) are applied through a
lookup with an empty fallback, so unseen countries simply skip that step.
"""
import re
from multiprocessing import Pool

import polars as pl
from unidecode import unidecode

# Legal-form and filler tokens removed to obtain the "core" name.
LEGAL = set(
    "llc inc incorporated corp corporation co company ltd limited pvt private plc llp lp pc pllc "
    "pty sarl sas sa eurl sasu snc sci scp gmbh ag bv nv ltee lc pra li opc".split()
)
FILLER = set("the and of services service center centre group dba formerly sri smt shri ms messrs m/s".split())

US_STATES = {
    "al": "alabama", "ak": "alaska", "az": "arizona", "ar": "arkansas", "ca": "california",
    "co": "colorado", "ct": "connecticut", "de": "delaware", "fl": "florida", "ga": "georgia",
    "hi": "hawaii", "id": "idaho", "il": "illinois", "in": "indiana", "ia": "iowa", "ks": "kansas",
    "ky": "kentucky", "la": "louisiana", "me": "maine", "md": "maryland", "ma": "massachusetts",
    "mi": "michigan", "mn": "minnesota", "ms": "mississippi", "mo": "missouri", "mt": "montana",
    "ne": "nebraska", "nv": "nevada", "nh": "new hampshire", "nj": "new jersey", "nm": "new mexico",
    "ny": "new york", "nc": "north carolina", "nd": "north dakota", "oh": "ohio", "ok": "oklahoma",
    "or": "oregon", "pa": "pennsylvania", "ri": "rhode island", "sc": "south carolina",
    "sd": "south dakota", "tn": "tennessee", "tx": "texas", "ut": "utah", "vt": "vermont",
    "va": "virginia", "wa": "washington", "wv": "west virginia", "wi": "wisconsin", "wy": "wyoming",
    "dc": "district of columbia", "pr": "puerto rico",
}
IN_STATES = {
    "mh": "maharashtra", "ka": "karnataka", "tn": "tamil nadu", "wb": "west bengal", "dl": "delhi",
    "up": "uttar pradesh", "gj": "gujarat", "rj": "rajasthan", "mp": "madhya pradesh",
    "ap": "andhra pradesh", "ts": "telangana", "tg": "telangana", "kl": "kerala", "pb": "punjab",
    "hr": "haryana", "br": "bihar", "or": "odisha", "od": "odisha", "jh": "jharkhand",
    "cg": "chhattisgarh", "ct": "chhattisgarh", "uk": "uttarakhand", "ua": "uttarakhand",
    "hp": "himachal pradesh", "jk": "jammu and kashmir", "as": "assam", "ga": "goa",
    "ch": "chandigarh", "py": "puducherry", "mn": "manipur", "ml": "meghalaya", "mz": "mizoram",
    "nl": "nagaland", "sk": "sikkim", "tr": "tripura", "ar": "arunachal pradesh",
    "an": "andaman and nicobar islands", "ld": "lakshadweep", "orissa": "odisha",
    "new delhi": "delhi", "bengaluru": "bangalore", "mumbai suburban": "mumbai",
}
STATE_MAPS = {"US": US_STATES, "India": IN_STATES}

# Native-script state names seen in Indian addresses -> English (applied before transliteration).
INDIC_STATES = {
    "महाराष्ट्र": "maharashtra", "कर्नाटक": "karnataka", "ಕರ್ನಾಟಕ": "karnataka", "தமிழ்நாடு": "tamil nadu",
    "தமிழ் நாடு": "tamil nadu", "পশ্চিমবঙ্গ": "west bengal", "दिल्ली": "delhi", "उत्तर प्रदेश": "uttar pradesh",
    "गुजरात": "gujarat", "ગુજરાત": "gujarat", "राजस्थान": "rajasthan", "मध्य प्रदेश": "madhya pradesh",
    "తెలంగాణ": "telangana", "ఆంధ్ర ప్రదేశ్": "andhra pradesh", "ఆంధ్రప్రదేశ్": "andhra pradesh",
    "കേരളം": "kerala", "ਪੰਜਾਬ": "punjab", "हरियाणा": "haryana", "बिहार": "bihar", "ଓଡ଼ିଶା": "odisha",
    "ଓଡିଶା": "odisha", "झारखंड": "jharkhand", "छत्तीसगढ़": "chhattisgarh", "उत्तराखंड": "uttarakhand",
    "हिमाचल प्रदेश": "himachal pradesh", "असम": "assam", "অসম": "assam", "गोवा": "goa", "पंजाब": "punjab",
    "चंडीगढ़": "chandigarh", "जम्मू और कश्मीर": "jammu and kashmir", "मुंबई": "mumbai", "पुणे": "pune",
    "बेंगलुरु": "bangalore", "ಬೆಂಗಳೂರು": "bangalore", "चेन्नई": "chennai", "சென்னை": "chennai",
    "कोलकाता": "kolkata", "কলকাতা": "kolkata", "हैदराबाद": "hyderabad", "హైదరాబాద్": "hyderabad",
    "अहमदाबाद": "ahmedabad", "અમદાવાદ": "ahmedabad", "नई दिल्ली": "new delhi", "नागपुर": "nagpur",
}

ADDR_ABBR = {
    "st": "street", "rd": "road", "ave": "avenue", "av": "avenue", "dr": "drive", "ln": "lane",
    "ct": "court", "cir": "circle", "blvd": "boulevard", "bd": "boulevard", "hwy": "highway",
    "pkwy": "parkway", "pl": "place", "ter": "terrace", "terr": "terrace", "trl": "trail",
    "twp": "township", "apt": "apartment", "ste": "suite", "fl": "floor", "flr": "floor",
    "bldg": "building", "mt": "mount", "ft": "fort", "n": "north", "s": "south", "e": "east",
    "w": "west", "ne": "northeast", "nw": "northwest", "se": "southeast", "sw": "southwest",
    "nr": "near", "opp": "opposite", "indl": "industrial", "ind": "industrial", "sec": "sector",
    "blk": "block", "res": "residency", "soc": "society", "rly": "railway", "stn": "station",
    "dist": "district", "tal": "taluka", "vill": "village", "po": "post", "hno": "house",
    "rte": "route", "cres": "crescent", "sq": "square", "chs": "chs", "ext": "extension",
    "ph": "phase", "nagar": "nagar", "clny": "colony", "mkt": "market", "gr": "ground",
}

_DOMAIN_RE = re.compile(r"(?:https?://)?(?:www\.)?([a-z0-9-]{2,})\.(?:co\.in|co\.uk|com|in|org|net|co|biz|info|us|fr|io)\b")
_DOT_ABBR_RE = re.compile(r"\b([a-z])\.(?=[a-z]\b)")
_NONALNUM_RE = re.compile(r"[^a-z0-9]+")
_ZERO_RE = re.compile(r"(?<=[a-z])0|0(?=[a-z])")
_FIVE_RE = re.compile(r"(?<=[a-z])5(?=[a-z])|(?<![a-z0-9])5(?=[a-z]{2})")
_NUM_RE = re.compile(r"\d+")
_COMP_SPLIT_RE = re.compile(r"[,;|]")


def norm_name(raw: str):
    """Return (full_norm, core, core_nospace, is_domain, nonlatin)."""
    nonlatin = 0 if raw.isascii() else 1
    s = raw if not nonlatin else unidecode(raw)
    s = s.lower().replace("&", " and ")
    is_domain = 0
    if "." in s:
        s2 = _DOMAIN_RE.sub(lambda m: " " + m.group(1).replace("-", "") + " ", s)
        if s2 != s:
            is_domain, s = 1, s2
        for _ in range(3):  # l.l.c. -> llc, d.b.a. -> dba
            s = _DOT_ABBR_RE.sub(r"\1", s)
    s = _NONALNUM_RE.sub(" ", s).strip()
    s = _FIVE_RE.sub("s", _ZERO_RE.sub("o", s))
    toks = s.split()
    core = [t for t in toks if t not in LEGAL and t not in FILLER]
    core = [t for i, t in enumerate(core) if i == 0 or t != core[i - 1]]  # drop stutter duplicates
    if not core:
        core = toks
    full = " ".join(toks)
    core_s = " ".join(core)
    return full, core_s, core_s.replace(" ", ""), is_domain, nonlatin


def norm_addr(raw: str, country: str):
    """Return (normalised address string, list of numeric tokens)."""
    nums = _NUM_RE.findall(raw)
    s = raw
    if not s.isascii():
        for k, v in INDIC_STATES.items():
            if k in s:
                s = s.replace(k, " " + v + " ")
        s = unidecode(s)
    s = s.lower()
    smap = STATE_MAPS.get(country, {})
    out = []
    for comp in _COMP_SPLIT_RE.split(s):
        c = _NONALNUM_RE.sub(" ", comp).strip()
        if not c:
            continue
        if c in smap:
            out.append(smap[c])
            continue
        out.append(" ".join(ADDR_ABBR.get(t, t) for t in c.split()))
    return " ".join(out), nums


def _norm_chunk(args):
    names, addrs, countries = args
    rows = []
    for n, a, c in zip(names, addrs, countries):
        full, core, core_ns, is_dom, nonlat = norm_name(n)
        naddr, nums = norm_addr(a, c)
        rows.append((full, core, core_ns, is_dom, nonlat, naddr, nums, int(a.strip() == "")))
    return rows


def normalize_frame(df: pl.DataFrame, procs: int = 4, chunk: int = 200_000) -> pl.DataFrame:
    """Add normalised columns to a source frame (entity_id, business_name, business_address, country)."""
    cols = ["nname", "core", "core_ns", "is_domain", "nonlatin", "naddr", "nums", "addr_empty"]
    schema = {"nname": pl.Utf8, "core": pl.Utf8, "core_ns": pl.Utf8, "is_domain": pl.Int8,
              "nonlatin": pl.Int8, "naddr": pl.Utf8, "nums": pl.List(pl.Utf8), "addr_empty": pl.Int8}

    def jobs():  # materialise one slice at a time so Python-object memory stays bounded
        for i in range(0, df.height, chunk):
            part = df.slice(i, chunk)
            yield (part["business_name"].to_list(), part["business_address"].to_list(), part["country"].to_list())

    def to_frame(rows):
        return pl.DataFrame({c: [r[i] for r in rows] for i, c in enumerate(cols)}, schema=schema)

    if procs > 1 and df.height > chunk:
        with Pool(procs) as pool:
            frames = [to_frame(part) for part in pool.imap(_norm_chunk, jobs(), chunksize=1)]
    else:
        frames = [to_frame(_norm_chunk(j)) for j in jobs()]
    extra = pl.concat(frames) if frames else pl.DataFrame(schema=schema)
    out = pl.concat([df, extra], how="horizontal")
    return out.with_columns(both=(pl.col("core") + " " + pl.col("naddr")).str.strip_chars())
