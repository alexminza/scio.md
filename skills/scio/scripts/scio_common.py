"""Shared constants for the skill's scripts. One User-Agent for everything that talks to scio.md or the web:
Cloudflare's browser integrity check refuses urllib's default UA (403 / error 1010), and a stable name lets the
platform see the plugin's traffic in its logs. The version comes from SKILL.md's frontmatter so it moves with the skill."""
import os, re

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
