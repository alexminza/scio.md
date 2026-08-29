"""Shared constants for the skill's scripts. One User-Agent for everything that talks to scio.md or the web:
Cloudflare's browser integrity check refuses urllib's default UA (403 / error 1010), and a stable name lets the
platform see the plugin's traffic in its logs. The version comes from SKILL.md's frontmatter so it moves with the skill."""
import os, re, urllib.error, urllib.request
from urllib.parse import urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))


def skill_version():
    try:
        fm = open(os.path.join(_HERE, "..", "SKILL.md"), encoding="utf-8").read().split("\n---\n", 1)[0]
        m = re.search(r'^\s*version:\s*"?(\d+\.\d+(?:\.\d+)?)', fm, flags=re.M)
        if m:
            return m.group(1)
    except OSError:
        pass
    return "0.1"


USER_AGENT = f"ScioSkill/{skill_version()} (+https://scio.md)"


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only to the same scheme, host and port: the platform's API never redirects elsewhere, and a hop
    to another host is where a bearer header would leak (the header is added unredirected too — belt and braces)."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        a, b = urlparse(req.full_url), urlparse(newurl)
        if (a.scheme, a.hostname, a.port) != (b.scheme, b.hostname, b.port):
            raise urllib.error.HTTPError(newurl, code, f"refused cross-host redirect to {b.hostname}", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(_SameHostRedirect)
