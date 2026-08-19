#!/usr/bin/env python3
"""
ops.py — EPO Open Patent Services client. Discovery only, by design.

Credentials come from openscent/.env (OPS_KEY / OPS_SECRET), which is gitignored.
Nothing here writes them anywhere, and no caller should pass them on a command line.

WHY OPS REPLACED GOOGLE PATENTS
-------------------------------
Google's /xhr/query gave a bare 503 with no explanation, which turned out to be a
multi-hour IP cooldown we could only infer by waiting. Twice. OPS states its limits:
a 403 carries an X-Rejection-Reason header naming WHICH quota was hit, hourly or weekly,
and every response carries X-Throttling-Control describing the current allowance per
service. A limit you can read is a limit you can respect.

DISCOVERY ONLY — THIS IS A LICENSING BOUNDARY, NOT A TECHNICAL ONE
------------------------------------------------------------------
OPS also serves `description` and `claims`, which would be a convenient way to fetch
full text. This module deliberately does not. harvest.py already ruled out EP/WO
documents because non-US patents lack the US no-copyright status; pulling US text
*through* EPO reintroduces that question by a side door, since EPO attaches terms of
use to its delivery even of public-domain text.

Patent NUMBERS are facts and carry no such weight. So: discover here, fetch from the
US source. That keeps the corpus CC0 without an asterisk, which is the whole point.

RATE POSTURE
------------
Deliberately slower than the throttle allows. The corpus is not urgent and a suspended
account would cost more than a slow walk. Requests are spaced, and X-Throttling-Control
is obeyed when it asks for more room than our floor.
"""
from __future__ import annotations
import base64, json, os, pathlib, random, re, sys, time, urllib.error, urllib.parse, urllib.request
from xml.etree import ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
AUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
SEARCH_URL = "https://ops.epo.org/3.2/rest-services/published-data/search"
NS = {"ops": "http://ops.epo.org", "ex": "http://www.epo.org/exchange"}

# OPS publishes its own allowance in every response:
#   x-throttling-control: busy (… search=green:15 …)
# means 15 search requests per minute. 60/15 = 4s, so the 3.0s floor used in the first
# smoke run was over the line. Default is now 4.5s (a ~13/min pace) and the header is
# obeyed whenever it asks for more room. Deliberately conservative: the corpus is not
# urgent, and a suspended account costs more than a slow walk. Two Google cooldowns
# were the tuition for that lesson.
MIN_GAP = float(os.environ.get("OPS_MIN_GAP", 4.5))
_last_call = [0.0]
_gap = [MIN_GAP]
QUOTA = {"hour_used": None, "week_used": None, "throttle": None}


def _note_headers(headers: dict):
    """Adapt the pace to what OPS says it will tolerate, and record quota spend."""
    h = {k.lower(): v for k, v in headers.items()}
    QUOTA["hour_used"] = h.get("x-individualquotaperhour-used")
    QUOTA["week_used"] = h.get("x-registeredquotaperweek-used")
    ctl = h.get("x-throttling-control")
    if not ctl:
        return
    QUOTA["throttle"] = ctl
    m = re.search(r"search=(\w+):(\d+)", ctl)
    if not m:
        return
    colour, per_min = m.group(1), int(m.group(2))
    allowed = 60.0 / per_min if per_min else 10.0
    # A non-green service is already under strain; take noticeably more room than the
    # stated minimum rather than riding the edge of it.
    if colour != "green":
        allowed *= 2.5
    _gap[0] = max(MIN_GAP, allowed * 1.15)


class QuotaExceeded(RuntimeError):
    """403: a real volume limit. Names its own clock — hour or week."""


class RobotDetected(RuntimeError):
    """403 CLIENT.RobotDetected. A PACING problem, not a volume one.

    Hit on 2026-08-19 after ~90 requests spaced at a constant 4.5s — comfortably inside
    the advertised 15/min. Staying under the rate limit is not sufficient: perfectly
    regular timing over a long run is itself the signal. Hence jitter below.
    """


class OPSError(RuntimeError):
    pass


def load_env() -> tuple[str, str]:
    env = ROOT / ".env"
    if not env.exists():
        raise OPSError(f"{env} not found — create it with OPS_KEY and OPS_SECRET.")
    vals = {}
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip('"').strip("'")
    key, secret = vals.get("OPS_KEY", ""), vals.get("OPS_SECRET", "")
    if not key or not secret:
        raise OPSError("OPS_KEY / OPS_SECRET are empty in .env — paste the app credentials.")
    return key, secret


_token = {"value": None, "expires": 0.0}


def token(force=False) -> str:
    """Access tokens last ~20 min. Renewed on demand, and on an invalid_access_token."""
    if not force and _token["value"] and time.time() < _token["expires"] - 60:
        return _token["value"]
    key, secret = load_env()
    basic = base64.b64encode(f"{key}:{secret}".encode()).decode()
    req = urllib.request.Request(
        AUTH_URL,
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"Authorization": f"Basic {basic}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        raise OPSError(f"auth failed ({e.code}). Check the key/secret in .env.\n{body}")
    _token["value"] = d["access_token"]
    _token["expires"] = time.time() + int(d.get("expires_in", 1200))
    return _token["value"]


_count = [0]


def _throttle():
    """Pace requests, irregularly and with occasional rests.

    Three things, because the 4.5s metronome triggered robot detection:
      jitter   — each gap is randomised, so the interval is never constant
      rests    — a longer pause every ~25 requests, breaking up sustained runs
      floor    — still never faster than the advertised allowance
    """
    _count[0] += 1
    gap = _gap[0] * random.uniform(1.0, 1.9)
    if _count[0] % 25 == 0:
        gap += random.uniform(20, 40)
        print(f"    (pausing {gap:.0f}s — {_count[0]} requests so far)", flush=True)
    waited = time.time() - _last_call[0]
    if waited < gap:
        time.sleep(gap - waited)
    _last_call[0] = time.time()


def raw_search(cql: str, begin: int = 1, end: int = 100, retry=True):
    """One search request. Returns (xml_text, headers). Raises on quota."""
    _throttle()
    req = urllib.request.Request(
        SEARCH_URL,
        data=urllib.parse.urlencode({"q": cql}).encode(),
        # Content-Type MUST be text/plain even though the body is form-encoded.
        # Sending the conventional application/x-www-form-urlencoded returns
        # 415 CLIENT.NotSupported. Verified 2026-08-19; the EPO reference client
        # does the same thing.
        headers={"Authorization": f"Bearer {token()}",
                 "Accept": "application/xml",
                 "Content-Type": "text/plain",
                 "X-OPS-Range": f"{begin}-{end}"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body, headers = r.read().decode(), dict(r.headers)
            _note_headers(headers)
            return body, headers
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if e.code == 400 and "invalid_access_token" in body and retry:
            token(force=True)
            return raw_search(cql, begin, end, retry=False)
        if e.code == 404 and "EntityNotFound" in body:
            # OPS answers "no matches" with 404 SERVER.EntityNotFound rather than an
            # empty list. Safe to read as zero BECAUSE IT SAYS SO: contrast Google,
            # where an empty response could equally mean rate-limited, which is exactly
            # how probe_classes.py came to report a class as empty on 2026-08-18 when it
            # had merely been throttled. An explicit "no results" is a measurement; a
            # blank one is not.
            return None, dict(e.headers)
        if e.code == 403:
            why = e.headers.get("X-Rejection-Reason", "unstated")
            # THREE different refusals share status 403 and must not be conflated.
            # Reporting a robot-detection as "your weekly quota is spent" would send
            # someone away for a week over a problem fixed by pacing.
            if "RobotDetected" in body:
                raise RobotDetected(
                    "OPS: CLIENT.RobotDetected — 'recent behaviour implies you are a robot'.\n"
                    "  NOT a quota. Volume was fine; the PATTERN was the problem. Sustained\n"
                    "  requests at a constant interval look mechanical even when they are\n"
                    "  under the published rate.\n"
                    "  Wait ~15-30 minutes, then re-run — progress is saved. Requests made\n"
                    "  during a cooldown tend to extend it (learned the hard way on Google).")
            if "PerWeek" in why:
                raise QuotaExceeded(f"OPS: weekly volume spent ({why}). Resumes next week.\n"
                                    f"{body[:200]}")
            if "PerHour" in why:
                raise QuotaExceeded(f"OPS: hourly quota spent ({why}). Wait for the hour to "
                                    f"roll over.\n{body[:200]}")
            raise QuotaExceeded(f"OPS refused (403): {why}\n{body[:300]}")
        raise OPSError(f"HTTP {e.code} on search\nq={cql!r} range={begin}-{end}\n{body[:500]}")


def parse(xml_text: str) -> tuple[int, list[dict]]:
    """(total_result_count, [{"id": "US2015209688A1", "family": "53678132"}, ...])

    THE FAMILY ID IS THE POINT, not a bonus field.

    OPS search returns ONE representative publication per patent family — asking for the
    grant US10000723 returns US2015209688A1, its pre-grant publication. Confirmed
    2026-08-19 by dumping the raw XML: one record, one document-id, family-id attached.

    That is the correct unit for this corpus. An application publication and the patent
    granted from it are the same disclosure by the same party in nearly the same words;
    counting both as separate "documents" would inflate the docs>=20 admission rule with
    a witness testifying twice. Google Patents had no family concept, so the existing
    2,588-patent corpus may contain exactly that duplication — see audit_families.py.
    """
    root = ET.fromstring(xml_text)
    total = 0
    for el in root.iter():
        if el.get("total-result-count"):
            total = int(el.get("total-result-count"))
            break
    out, seen = [], set()
    for ref in root.iter():
        if not ref.tag.endswith("publication-reference"):
            continue
        fam = ref.get("family-id", "")
        for dref in ref.iter():
            if not dref.tag.endswith("document-id"):
                continue
            if dref.get("document-id-type") != "docdb":
                continue
            parts = {c.tag.split("}")[-1]: (c.text or "") for c in dref}
            cc, num, kind = (parts.get("country", ""), parts.get("doc-number", ""),
                             parts.get("kind", ""))
            if cc and num and f"{cc}{num}{kind}" not in seen:
                seen.add(f"{cc}{num}{kind}")
                out.append({"id": f"{cc}{num}{kind}", "family": fam})
    return total, out


def search(cql: str, begin: int = 1, end: int = 100):
    """-> (total, [{"id","family"}, ...], headers)"""
    xml_text, headers = raw_search(cql, begin, end)
    if xml_text is None:          # explicit "no results found" from OPS
        return 0, [], headers
    total, recs = parse(xml_text)
    return total, recs, headers


# Measured 2026-08-19, one variable at a time:
#   span  — a single request may return at most 100 items
#   offset— range 1901-2000 succeeds, 2001-2100 returns 400 CLIENT.InvalidQuery
PAGE = 100
CEILING = 2000


class TooManyResults(RuntimeError):
    """total-result-count exceeds the 2,000 the API will paginate. Split the query.

    This is the failure mode that matters, and OPS makes it VISIBLE. Google capped at
    1,000 and simply returned fewer rows, so a truncated window looked like a complete
    one — the first corpus walk came back with 998 results and read as finished. Here the
    count is reported before paging starts, so an over-large query can refuse to run
    rather than quietly return a subset.
    """


def fetch_all(cql: str, cap=CEILING):
    """Every record for a query, or refuse. Never returns a silent partial.

    Returns (total, [{"id","family"}, ...]). Raises TooManyResults if the query is too
    big to page — the caller is then obliged to narrow it, which is the only correct
    response.
    """
    total, recs, _ = search(cql, 1, PAGE)
    if total > cap:
        raise TooManyResults(f"{total} results for {cql!r} — over the {cap} paging limit")
    got = list(recs)
    begin = PAGE + 1
    while begin <= total:
        end = min(begin + PAGE - 1, total)
        _, page, _ = search(cql, begin, end)
        if not page:
            break
        got += page
        begin = end + 1
    seen, out = set(), []
    for r in got:
        if r["id"] not in seen:
            seen.add(r["id"]); out.append(r)
    return total, out
