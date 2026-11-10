"""Módulo de circuitos.

AVISO DE DADOS: os comprimentos totais e o número de curvas são valores publicados dos circuitos
(conferir na FIA/FOM para a temporada escolhida). A GEOMETRIA (sequência de retas e raios de curva)
é um modelo ESQUEMÁTICO ESTIMADO, construído para reproduzir o comprimento total e fechar o traçado;
NÃO são coordenadas oficiais nem levantamento topográfico. Elevação: não disponível (gradiente = 0).
Para usar dados reais, importe um CSV (x, y) com ``Track.from_xy`` ou substitua o campo ``layout``.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np

# Layout: tokens "S<m>" reta; "R<raio>:<graus>" curva à direita; "L<raio>:<graus>" curva à esquerda.
# 'dir' do circuito: +1 horário, -1 anti-horário (sentido dominante, apenas para fechar o laço).
_C = {}


def _add(key, name, country, length_m, turns, altitude_m, laps, abrasive, grip, direction, layout, note=""):
    _C[key] = dict(key=key, name=name, country=country, length_m=length_m, turns=turns, altitude_m=altitude_m,
                   race_laps=laps, abrasiveness=abrasive, asphalt_grip=grip, direction=direction, layout=layout, note=note)


_add("interlagos", "Autódromo José Carlos Pace (Interlagos)", "Brasil", 4309, 15, 760, 71, 1.00, 1.00, -1,
     "S320 L55:95 R80:70 S120 L60:85 R45:55 L180:55 S380 L110:35 R70:95 S110 L50:60 L65:90 S520 L190:42 L55:105 S210")
_add("monza", "Autodromo Nazionale Monza", "Itália", 5793, 11, 162, 53, 0.85, 1.00, 1,
     "S980 R45:55 R45:55 S320 R320:65 S560 L50:42 R50:42 S280 R95:75 S260 R75:85 S850 L55:55 R55:60 L55:40 S420 R65:60 S300")
_add("spa", "Circuit de Spa-Francorchamps", "Bélgica", 7004, 19, 400, 44, 1.00, 1.00, 1,
     "S400 R30:150 L120:45 R250:55 S800 R60:75 S400 L150:40 R170:35 S650 L110:50 R90:65 S300 L130:40 S900 R100:45 L80:40 S450 R40:70 R40:60 S700 L40:60 R40:60 S620")
_add("silverstone", "Silverstone Circuit", "Reino Unido", 5891, 18, 150, 52, 1.20, 1.00, 1,
     "S350 R70:80 L65:60 R150:50 S400 R85:90 S300 L170:45 R170:60 L170:45 S120 R90:55 L90:70 S1100 R55:120 S400 R120:45 L65:70 S350 R100:90 S420 R210:60")
_add("suzuka", "Suzuka International Racing Course", "Japão", 5807, 18, 45, 53, 1.10, 1.00, 1,
     "S500 R70:100 R80:50 S150 L140:55 R160:60 L130:50 R100:40 S250 L220:25 R50:150 S380 L90:60 S800 R140:50 L100:40 S230 R40:150 S380 R130:85 S520 R55:60 L55:70 S350")
_add("monaco", "Circuit de Monaco", "Mônaco", 3337, 19, 10, 78, 0.80, 0.97, 1,
     "S520 R45:80 L55:70 S120 R60:90 S140 L35:60 R30:50 S190 R90:50 L30:70 R25:150 S110 L55:80 R55:80 S260 R25:90 S120 L25:70 R45:60 S110 R40:90 S300")
_add("barcelona", "Circuit de Barcelona-Catalunya", "Espanha", 4657, 14, 100, 66, 1.15, 1.00, 1,
     "S1050 R70:100 L95:60 R170:55 S250 R120:90 R85:60 S320 L110:90 S520 R80:50 L45:90 S190 R75:60 R60:55 S350 R75:70 R50:80 S450")
_add("zandvoort", "Circuit Zandvoort", "Países Baixos", 4259, 14, 5, 72, 1.05, 1.00, 1,
     "S360 R35:100 S160 L50:95 R75:65 S220 L90:45 R100:60 S250 L55:90 S190 R50:100 R90:45 S280 L65:60 R60:70 S280 R90:60 R55:80 S360")
_add("lasvegas", "Las Vegas Strip Circuit", "EUA", 6201, 17, 610, 50, 0.85, 0.93, -1,
     "S1300 L50:90 R50:90 S350 L60:75 S1900 L90:75 L90:50 S360 L55:90 R55:90 S400 L70:70 S780 L60:70 S350")
_add("austin", "Circuit of The Americas", "EUA", 5513, 20, 160, 56, 1.00, 1.00, -1,
     "S600 L55:110 R120:70 S130 L90:60 R120:45 L90:50 R80:50 S200 L70:60 S780 L40:100 L45:60 S320 R85:70 S110 L120:30 R150:55 S330 L60:80 L110:60 S700 L45:70 R55:80 L170:50 S260")
_add("miami", "Miami International Autodrome", "EUA", 5412, 19, 2, 57, 0.90, 0.97, -1,
     "S900 R60:90 L60:75 S300 R90:70 R95:60 R100:55 S600 R50:90 S260 L55:90 R55:70 S1100 R70:95 S200 R45:90 L70:80 S340 R120:50 S450 L90:60 S300")
_add("melbourne", "Albert Park Circuit", "Austrália", 5278, 14, 10, 58, 0.90, 0.98, -1,
     "S800 R70:90 R85:55 S750 R50:80 S280 R95:45 L180:45 S600 R60:70 L110:35 S450 L90:80 R120:45 S520 R50:80 R90:50 S300")
_add("bahrain", "Bahrain International Circuit", "Bahrein", 5412, 15, 10, 57, 1.20, 1.00, 1,
     "S860 R60:100 L70:65 L50:75 S210 R45:110 S350 R180:35 L80:60 S650 R45:150 S340 R115:55 L110:45 S280 R65:60 R55:90 S900 L60:85 R90:55 S280")
_add("jeddah", "Jeddah Corniche Circuit", "Arábia Saudita", 6174, 27, 5, 50, 0.85, 0.95, -1,
     "S650 L70:70 L85:55 L85:60 R100:50 S520 L110:40 R130:45 S380 L180:35 R170:35 S550 L120:50 R160:30 S450 L90:60 R100:50 S800 L90:60 R150:40 S620 L55:90 R120:45 S350 L80:85 S560")
_add("abudhabi", "Yas Marina Circuit", "Emirados Árabes", 5281, 16, 5, 58, 0.90, 0.98, 1,
     "S1150 R70:90 L100:60 R130:50 S330 L65:80 R80:50 S870 R50:85 S220 R45:90 R45:70 S760 L60:60 R65:80 S280 R55:70 L45:80 R55:60 S200")


@dataclass
class Segment:
    kind: str            # 'straight' | 'corner'
    name: str
    s0: float
    s1: float
    radius: float = 0.0  # 0 para reta
    direction: int = 0   # +1 direita, -1 esquerda

    @property
    def length(self) -> float:
        return self.s1 - self.s0


@dataclass
class Track:
    key: str
    name: str
    country: str
    season: str
    length_m: float
    turns_official: int
    altitude_m: float
    race_laps: int
    abrasiveness: float
    asphalt_grip: float
    segments: list[Segment]
    x: np.ndarray                 # pontos do traçado (vértices) em metros
    y: np.ndarray
    s: np.ndarray                 # abscissa dos vértices
    kappa_fn_s: np.ndarray        # fronteiras de segmentos
    data_source: str = "Geometria esquemática ESTIMADA; comprimento total conforme publicado (conferir)"
    elevation_available: bool = False
    sector_fracs: tuple = (1 / 3, 2 / 3)
    note: str = ""

    # ----------------------------------------------------------------- discretização
    def discretize(self, ds: float = 6.0, smooth_m: float = 18.0):
        """Retorna dict com arrays por ponto: s, x, y, kappa (1/m, assinado), seg_id, heading."""
        n = max(int(round(self.length_m / ds)), 50)
        ds = self.length_m / n
        s = (np.arange(n) + 0.5) * ds
        kappa = np.zeros(n)
        seg_id = np.zeros(n, dtype=int)
        for k, sg in enumerate(self.segments):
            m = (s >= sg.s0) & (s < sg.s1)
            seg_id[m] = k
            if sg.kind == "corner":
                kappa[m] = sg.direction / sg.radius
        # suavização leve (transições de curvatura não são degraus)
        w = max(int(smooth_m / ds), 1)
        if w > 1:
            ker = np.ones(w) / w
            kp = np.concatenate([kappa[-w:], kappa, kappa[:w]])
            kappa = np.convolve(kp, ker, mode="same")[w:-w]
        # posição por interpolação periódica dos vértices
        xs = np.interp(s, self.s, self.x)
        ys = np.interp(s, self.s, self.y)
        heading = np.unwrap(np.arctan2(np.gradient(ys), np.gradient(xs)))
        return dict(s=s, ds=ds, n=n, x=xs, y=ys, kappa=kappa, seg_id=seg_id, heading=heading,
                    grad=np.zeros(n))

    def sector_bounds(self):
        return [0.0, self.sector_fracs[0] * self.length_m, self.sector_fracs[1] * self.length_m, self.length_m]

    @staticmethod
    def from_xy(key, name, xy: np.ndarray, **kw) -> "Track":
        """Cria pista a partir de coordenadas reais (n,2) em metros (traçado fechado)."""
        xy = np.asarray(xy, float)
        d = np.hypot(*np.diff(np.vstack([xy, xy[:1]]), axis=0).T)
        s = np.concatenate([[0], np.cumsum(d)])
        L = float(s[-1])
        pts = np.vstack([xy, xy[:1]])
        # raio local pela curvatura discreta (3 pontos)
        h = np.unwrap(np.arctan2(np.gradient(pts[:, 1]), np.gradient(pts[:, 0])))
        k = np.gradient(h, s)
        segs, cur = [], 0
        thr = 1 / 800.0
        is_c = np.abs(k) > thr
        i0 = 0
        for i in range(1, len(s)):
            if is_c[i] != is_c[i - 1] or i == len(s) - 1:
                seg_k = float(np.mean(k[i0:i + 1]))
                if is_c[i0]:
                    segs.append(Segment("corner", "", s[i0], s[i], 1 / max(abs(seg_k), 1e-4), int(np.sign(seg_k))))
                else:
                    segs.append(Segment("straight", "", s[i0], s[i]))
                i0 = i
        _name_segments(segs)
        return Track(key, name, kw.get("country", "-"), kw.get("season", "-"), L, kw.get("turns", 0),
                     kw.get("altitude_m", 0.0), kw.get("race_laps", int(math.ceil(305000 / L))), 1.0, 1.0,
                     segs, pts[:, 0], pts[:, 1], s, s, data_source=kw.get("data_source", "coordenadas importadas"))


def _name_segments(segs):
    ci = si = 0
    for sg in segs:
        if sg.kind == "corner":
            ci += 1
            sg.name = f"Curva {ci}"
        else:
            si += 1
            sg.name = f"Reta {si}"


def _parse(layout: str):
    out = []
    for tok in layout.split():
        if tok[0] == "S":
            out.append(["S", float(tok[1:])])
        else:
            r, a = tok[1:].split(":")
            out.append(["C", float(r), float(a) * (1 if tok[0] == "R" else -1)])
    return out


def _build(spec: dict, season: str) -> Track:
    items = _parse(spec["layout"])
    L = spec["length_m"]
    # fecha o giro total em ±360°: escala apenas as curvas do sentido dominante
    dirn = 1 if sum(it[2] for it in items if it[0] == "C") > 0 else -1
    dom = sum(abs(it[2]) for it in items if it[0] == "C" and it[2] * dirn > 0)
    oth = sum(abs(it[2]) for it in items if it[0] == "C" and it[2] * dirn < 0)
    f = (360.0 + oth) / dom
    for it in items:
        if it[0] == "C" and it[2] * dirn > 0:
            it[2] *= f
    arcs = sum(it[1] * math.radians(abs(it[2])) for it in items if it[0] == "C")
    S0 = np.array([it[1] for it in items if it[0] == "S"])
    # ângulo de proa no início de cada elemento
    head, hcur = [], 0.0
    for it in items:
        head.append(hcur)
        if it[0] == "C":
            hcur += math.radians(it[2])
    # integração direta (proa matemática: direita => proa decresce)
    def integrate(lengths):
        x = y = 0.0
        h = 0.0
        pts = [(0.0, 0.0)]
        k = 0
        for it in items:
            if it[0] == "S":
                Lk = lengths[k]; k += 1
                x += Lk * math.cos(h); y += Lk * math.sin(h)
                pts.append((x, y))
            else:
                R, ang = it[1], -math.radians(it[2])  # direita -> negativo
                n = max(int(abs(ang) / math.radians(5)), 2)
                for _ in range(n):
                    da = ang / n
                    # arco de raio R com giro da
                    sgn = 1 if da > 0 else -1
                    cx = x - sgn * R * math.sin(h); cy = y + sgn * R * math.cos(h)
                    h += da
                    x = cx + sgn * R * math.sin(h); y = cy - sgn * R * math.cos(h)
                    pts.append((x, y))
        return np.array(pts), (x, y), h
    # fechamento: minimiza Σ ΔL²/S_i com restrições de posição e comprimento
    lengths = S0 * (L - arcs) / S0.sum()
    for _ in range(4):
        _, (ex, ey), _h = integrate(lengths)
        hs = [head[i] for i, it in enumerate(items) if it[0] == "S"]
        # proa matemática no início da reta i = -(proa de rótulo acumulada)
        u = np.array([[math.cos(-h), math.sin(-h)] for h in hs])
        A = np.vstack([u[:, 0], u[:, 1], np.ones(len(hs))])
        b = np.array([-ex, -ey, L - (lengths.sum() + arcs)])
        D = np.diag(lengths)
        dL = D @ A.T @ np.linalg.solve(A @ D @ A.T, b)
        lengths = lengths + dL
        if lengths.min() < 20:
            lengths = np.maximum(lengths, 20.0)
    pts, (ex, ey), _ = integrate(lengths)
    # resíduo mínimo restante (<~1 m) distribuído linearmente
    d = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
    s = np.concatenate([[0], np.cumsum(d)])
    frac = s / s[-1]
    pts[:, 0] -= ex * frac
    pts[:, 1] -= ey * frac
    d = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
    s = np.concatenate([[0], np.cumsum(d)])
    s *= L / s[-1]
    # segmentos com abscissa
    segs, pos, k = [], 0.0, 0
    for it in items:
        if it[0] == "S":
            segs.append(Segment("straight", "", pos, pos + lengths[k])); pos += lengths[k]; k += 1
        else:
            arc = it[1] * math.radians(abs(it[2]))
            segs.append(Segment("corner", "", pos, pos + arc, it[1], 1 if it[2] > 0 else -1)); pos += arc
    sc = L / pos
    for sg in segs:
        sg.s0 *= sc; sg.s1 *= sc
        if sg.kind == "corner":
            sg.radius *= sc
    _name_segments(segs)
    return Track(spec["key"], spec["name"], spec["country"], season, float(L), spec["turns"], spec["altitude_m"],
                 spec["race_laps"], spec["abrasiveness"], spec["asphalt_grip"], segs, pts[:, 0], pts[:, 1], s, s,
                 note=spec["note"])


def list_circuits() -> list[str]:
    return list(_C)


def get_track(key: str, season: str = "2025") -> Track:
    if key not in _C:
        raise KeyError(f"Circuito '{key}' desconhecido. Disponíveis: {list(_C)}")
    return _build(_C[key], season)


def register_circuit(key, name, country, length_m, turns, altitude_m, race_laps, layout, direction=1,
                     abrasiveness=1.0, asphalt_grip=1.0, note="definido pelo usuário"):
    """Adiciona/atualiza um circuito na lista (lista configurável, não limitada aos exemplos)."""
    _add(key, name, country, length_m, turns, altitude_m, race_laps, abrasiveness, asphalt_grip, direction, layout, note)
