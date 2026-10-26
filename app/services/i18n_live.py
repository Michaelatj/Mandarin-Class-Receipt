"""
services/i18n_live.py - the dictionary the browser uses to switch between
English and Mandarin without reloading the page.

It is built from the existing TRANSLATIONS table (one pair per key) plus the
extra sentences in ui_strings.py. Entries that contain {name} placeholders are
sent as patterns so text like "3 students registered" can be converted too.
"""
import json
import hashlib

from .i18n import TRANSLATIONS, _MONTH_KEYS, _DAY_KEYS
from .ui_strings import EXTRA

_cache = {}


def _build():
    en, zh = TRANSLATIONS["en"], TRANSLATIONS["zh"]
    pairs = {}
    for key, value in en.items():
        other = zh.get(key)
        if isinstance(value, str) and isinstance(other, str) and value.strip():
            pairs.setdefault(value.strip(), other.strip())
    pairs.update({k.strip(): v.strip() for k, v in EXTRA.items()})

    exact, patterns = {}, []
    for e, z in pairs.items():
        if e == z:
            continue
        if "{" in e and "}" in e:
            patterns.append([e, z])
        else:
            exact[e] = z

    zh_to_en = {}
    for e, z in exact.items():
        zh_to_en.setdefault(z, e)

    return {
        "en2zh": exact,
        "zh2en": zh_to_en,
        "patterns": patterns,
        "dates": {
            "en": {"days": [en[k] for k in _DAY_KEYS], "months": [en[k] for k in _MONTH_KEYS]},
            "zh": {"days": [zh[k] for k in _DAY_KEYS], "months": [zh[k] for k in _MONTH_KEYS]},
            "short": {
                "en_days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                "zh_days": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
                "en_months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                "zh_months": [str(n) + "月" for n in range(1, 13)],
            },
        },
    }


def data_js():
    """The dictionary as a script (cached for the life of the process)."""
    if "js" not in _cache:
        payload = json.dumps(_build(), ensure_ascii=False, separators=(",", ":"))
        _cache["js"] = "window.I18N_DATA=" + payload + ";"
        _cache["version"] = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
    return _cache["js"]


def version():
    data_js()
    return _cache["version"]
