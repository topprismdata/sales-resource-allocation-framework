"""纯几何原语（stdlib）：凸包 / 最小二乘直线 / 半平面裁剪 / 重心。

用于合同语义解析后的围栏构建：
  fence = convex_hull(街道多边形点集)  →  逐条界线半平面裁剪（Sutherland–Hodgman）
"""
from __future__ import annotations


def convex_hull(pts):
    """Andrew 单调链，输入 [(x,y)] → 逆时针外环 [(x,y)]（首尾不重复）。"""
    ps = sorted({(round(float(p[0]), 6), round(float(p[1]), 6)) for p in pts})
    if len(ps) <= 2:
        return ps

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in ps:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(ps):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def centroid(poly):
    n = len(poly)
    if n == 0:
        return (0.0, 0.0)
    return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)


def fit_line(pts):
    """最小二乘 y=kx+b（近竖直时改用 x=ky+b）。返回 (点, 法向量)——法向朝正侧。"""
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx >= syy:                       # 横卧线 y = k x + b
        k = sxy / sxx if sxx else 0.0
        # 法向量指向 y - kx 增大侧：(-k, 1)
        return ((mx, my), (-k, 1.0))
    k = sxy / syy if syy else 0.0        # 竖直线 x = k y + b → 法向 (1, -k)
    return ((mx, my), (1.0, -k))


def clip_halfplane(poly, point, normal):
    """Sutherland–Hodgman：保留 dot(p-point, normal) >= 0 的一侧。"""
    px, py = point
    nx, ny = normal

    def side(p):
        return (p[0] - px) * nx + (p[1] - py) * ny

    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        sa, sb = side(a), side(b)
        if sa >= 0:
            out.append(a)
        if (sa >= 0) != (sb >= 0):
            t = sa / (sa - sb)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def shoelace_area_km2(ring):
    s = 0.0
    lat_ref = sum(p[1] for p in ring) / max(len(ring), 1)
    px = [p[0] * 102.2 * __import__("math").cos(__import__("math").radians(lat_ref))
          for p in ring]
    py = [p[1] * 110.574 for p in ring]
    for i in range(len(ring)):
        j = (i + 1) % len(ring)
        s += px[i] * py[j] - px[j] * py[i]
    return abs(s) / 2
