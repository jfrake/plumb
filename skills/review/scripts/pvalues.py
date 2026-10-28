"""Shared p-value arithmetic for numbers read off a printed table. Standard library only.

Every number is taken as printed, so its rounding is known: a value printed with d decimals
lies within half_unit = 0.5 x 10^-d of the printed value. Checks built on these functions flag
a printed result only when it is wrong for every value the printed digits allow.

The core's verify_arithmetic.py uses this module. A pack script imports it with:

    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "skills" / "review" / "scripts"))
    import pvalues
"""
from __future__ import annotations

import math
import re

_NUMBER = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)$")


def parse_printed(text):
    """Return (value, half_unit) for a number as printed, such as "0.047", "-1.20", or ".05";
    None when the text is not a plain number."""
    s = str(text).strip().replace("−", "-").replace(",", "")
    if not _NUMBER.match(s):
        return None
    decimals = len(s.split(".", 1)[1]) if "." in s else 0
    return float(s), 0.5 * 10 ** -decimals


def abs_t_bounds(b, se):
    """|t| low and high for a printed coefficient b and standard error se (both text).
    high is math.inf when se minus its half unit is zero or less. None when either is not a number
    or se is not positive."""
    pb, ps = parse_printed(b), parse_printed(se)
    if pb is None or ps is None or ps[0] <= 0:
        return None
    (vb, hb), (vs, hs) = pb, ps
    low = max(0.0, abs(vb) - hb) / (vs + hs)
    high = (abs(vb) + hb) / (vs - hs) if vs - hs > 0 else math.inf
    return low, high


def abs_t_bounds_from_t(t):
    """|t| low and high for a printed t statistic (text). None when it is not a number."""
    pt = parse_printed(t)
    if pt is None:
        return None
    v, h = pt
    return max(0.0, abs(v) - h), abs(v) + h


def p_normal(t):
    """Two-sided p for |t| under the standard normal."""
    if math.isinf(t):
        return 0.0
    return math.erfc(abs(t) / math.sqrt(2))


def _betacf(a, b, x):
    """Continued fraction for the regularized incomplete beta (modified Lentz's method)."""
    tiny, eps = 1e-300, 3e-16
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 301):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betai(a, b, x):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def p_student(t, df):
    """Two-sided p for |t| under Student's t with df degrees of freedom: I_x(df/2, 1/2),
    x = df / (df + t^2)."""
    if df is None or math.isnan(df) or df <= 0:
        raise ValueError("df must be positive")
    if math.isinf(df):
        return p_normal(t)
    if math.isinf(t):
        return 0.0
    return _betai(df / 2.0, 0.5, df / (df + t * t))


def p_range(t_low, t_high, df=None, one_tailed=False):
    """The p interval for |t| in [t_low, t_high]: under the normal when df is None, else under t(df).
    one_tailed halves it."""
    f = p_normal if df is None else (lambda t: p_student(t, df))
    lo, hi = f(t_high), f(t_low)
    return (lo / 2, hi / 2) if one_tailed else (lo, hi)


def printed_p_range(text):
    """The interval a printed p-value stands for: "0.05" -> (0.045, 0.055); "< 0.001", "<.001",
    "p < 0.05", "<= 0.05" -> (0, v); "> 0.10", ">= 0.10" -> (v, 1). None when the text is not a
    p-value (not a plain number, outside [0, 1], or scientific notation), and for "< 0" or "> 1",
which bound nothing."""
    s = str(text).strip().replace("\u2212", "-").replace(" ", "")
    s = re.sub(r"^p(?=[<>=\u2264\u2265])", "", s, flags=re.I).lstrip("=")
    m = re.match(r"^(<=|>=|\u2264|\u2265|<|>)(.*)$", s)
    if m:
        p = parse_printed(m.group(2))
        if p is None or not 0.0 <= p[0] <= 1.0:
            return None
        below = m.group(1) in ("<", "<=", "\u2264")
        if (below and p[0] <= 0.0) or (not below and p[0] >= 1.0):
            return None
        return (0.0, p[0]) if below else (p[0], 1.0)
    p = parse_printed(s)
    if p is None or not 0.0 <= p[0] <= 1.0:
        return None
    v, h = p
    return max(0.0, v - h), min(1.0, v + h)
