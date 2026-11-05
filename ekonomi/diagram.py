"""Enkla SVG-diagram som ritas på servern (inga JavaScript-bibliotek)."""

from decimal import Decimal
from html import escape

from django.utils.safestring import mark_safe

FARGER = {"in": "#0f766e", "ut": "#e0794a", "budget": "#9aa5a2", "netto": "#2563eb", "skuld": "#b42318"}


def _kr(v):
    return f"{Decimal(v):,.0f}".replace(",", " ")


def _skala(maxv):
    if maxv <= 0:
        return 1000
    import math

    steg = 10 ** math.floor(math.log10(maxv))
    for f in (1, 2, 2.5, 5, 10):
        if maxv <= f * steg:
            return f * steg
    return 10 * steg


def stapel(etiketter, serier, hojd=220, bredd=760):
    """serier: [(namn, färg, [värden])] – grupperade staplar, värden ≥ 0."""
    v_alla = [float(v) for _, _, vs in serier for v in vs] or [0]
    topp = _skala(max(v_alla))
    vm, hm, ym, xm = 64, 12, 18, 22
    yta_b, yta_h = bredd - vm - hm, hojd - ym - xm
    n, k = len(etiketter), len(serier)
    grupp = yta_b / max(n, 1)
    sb = min(18, grupp * 0.8 / max(k, 1))
    delar = [f'<svg viewBox="0 0 {bredd} {hojd}" role="img" class="svgdiagram">']
    for i in range(5):
        v = topp * i / 4
        y = ym + yta_h - yta_h * i / 4
        delar.append(f'<line x1="{vm}" x2="{bredd - hm}" y1="{y:.1f}" y2="{y:.1f}" class="rut"/>'
                     f'<text x="{vm - 6}" y="{y + 4:.1f}" text-anchor="end" class="ax">{_kr(v)}</text>')
    for i, e in enumerate(etiketter):
        x0 = vm + grupp * i + (grupp - sb * k) / 2
        for j, (namn, farg, vs) in enumerate(serier):
            v = float(vs[i] or 0)
            h = yta_h * v / topp if topp else 0
            delar.append(f'<rect x="{x0 + j * sb:.1f}" y="{ym + yta_h - h:.1f}" width="{sb - 2:.1f}" height="{h:.1f}" '
                         f'rx="2" fill="{farg}"><title>{escape(str(e))} {escape(namn)}: {_kr(v)} kr</title></rect>')
        delar.append(f'<text x="{vm + grupp * i + grupp / 2:.1f}" y="{hojd - 5}" text-anchor="middle" class="ax">'
                     f'{escape(str(e))}</text>')
    delar.append("</svg>")
    return mark_safe("".join(delar))


def linje(etiketter, serier, hojd=240, bredd=760):
    """serier: [(namn, färg, [värden])] – värden får vara negativa."""
    v_alla = [float(v) for _, _, vs in serier for v in vs] or [0]
    lo, hi = min(0, min(v_alla)), max(0, max(v_alla))
    hi = _skala(hi) if hi > 0 else 0
    lo = -_skala(-lo) if lo < 0 else 0
    if hi == lo:
        hi = 1000
    vm, hm, ym, xm = 76, 12, 14, 22
    yta_b, yta_h = bredd - vm - hm, hojd - ym - xm
    n = len(etiketter)

    def y(v):
        return ym + yta_h * (hi - float(v)) / (hi - lo)

    def x(i):
        return vm + (yta_b * i / (n - 1) if n > 1 else yta_b / 2)

    delar = [f'<svg viewBox="0 0 {bredd} {hojd}" role="img" class="svgdiagram">']
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        delar.append(f'<line x1="{vm}" x2="{bredd - hm}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="rut"/>'
                     f'<text x="{vm - 6}" y="{y(v) + 4:.1f}" text-anchor="end" class="ax">{_kr(v)}</text>')
    steg = max(1, n // 12)
    for i, e in enumerate(etiketter):
        if i % steg == 0 or i == n - 1:
            delar.append(f'<text x="{x(i):.1f}" y="{hojd - 5}" text-anchor="middle" class="ax">{escape(str(e))}</text>')
    for namn, farg, vs in serier:
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vs))
        delar.append(f'<polyline points="{pts}" fill="none" stroke="{farg}" stroke-width="2.2"/>')
        for i, v in enumerate(vs):
            delar.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3" fill="{farg}">'
                         f'<title>{escape(str(etiketter[i]))} {escape(namn)}: {_kr(v)} kr</title></circle>')
    delar.append("</svg>")
    return mark_safe("".join(delar))
