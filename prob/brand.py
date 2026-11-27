"""The channel's mark (the sun and two open rings of the sky, the logo of @osmon_obhavo) drawn left of a video's or map's signature."""
import matplotlib.patches as mp


def brand(target, x, y, s, **kw):
    """Draw text `s` like target.text(x, y, s, **kw) and the Osmon mark just left of it (same height as the text, a little taller).
    target: an Axes or a Figure. Returns the text."""
    fig = target.figure if hasattr(target, 'transAxes') and target.figure is not None else target
    t = target.text(x, y, s, **kw)
    try:
        bb = t.get_window_extent(fig.canvas.get_renderer())
        h = bb.height * 1.55; yc = (bb.y0 + bb.y1) / 2
        x1 = (bb.x0 if kw.get('ha', 'left') != 'left' or True else bb.x0) - h * 0.3
        W, H = fig.bbox.width, fig.bbox.height
        a = fig.add_axes([(x1 - h) / W, (yc - h / 2) / H, h / W, h / H]); a.set_xlim(0, 100); a.set_ylim(0, 100); a.axis('off')
        a.set_zorder((kw.get('zorder') or 9) + 1); a.patch.set_alpha(0)
        ink = kw.get('color', '#8a96a3'); lw = h * 0.09 * 72 / fig.dpi
        for r in (22, 40):  # the gap faces up and to the right, like the logo
            a.add_patch(mp.Arc((50, 50), 2 * r, 2 * r, theta1=75, theta2=375, lw=lw, color=ink, capstyle='round'))
        a.add_patch(mp.Circle((50, 50), 10, color='#FFB020', lw=0))
    except Exception:
        pass
    return t


def mark(fig, cx, cy, size, ink='#ffffff', rings=(22, 40), zorder=30):
    """The Osmon mark centred at figure coordinates (cx, cy), `size` pixels across: open rings in `ink`, the amber sun in the middle."""
    W, H = fig.bbox.width, fig.bbox.height
    a = fig.add_axes([cx - size / 2 / W, cy - size / 2 / H, size / W, size / H]); a.set_xlim(0, 100); a.set_ylim(0, 100); a.axis('off')
    a.set_zorder(zorder); a.patch.set_alpha(0)
    lw = size * (0.09 if len(rings) == 2 else 0.07) * 72 / fig.dpi
    for r in rings:
        a.add_patch(mp.Arc((50, 50), 2 * r, 2 * r, theta1=75, theta2=375, lw=lw, color=ink, capstyle='round'))
    a.add_patch(mp.Circle((50, 50), 10 if len(rings) == 2 else 9, color='#FFB020', lw=0))
    return a
