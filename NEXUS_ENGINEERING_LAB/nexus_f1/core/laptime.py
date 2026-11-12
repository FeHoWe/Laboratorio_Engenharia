"""Simulador de tempo de volta (quase-estático, passes regressivo + progressivo).

Modelo (documentado e simplificado):
- Resistências: arrasto 0.5·ρ·CdA·v², rolamento Crr·(m·g + downforce).
- Carga por eixo: peso estático + downforce (distribuição aero) ± transferência longitudinal (m·ax·h/L)
  ± transferência lateral (m·ay·h/bitola, repartida por rigidez de rolagem). Sensibilidade à carga do pneu
  (pneu com carga maior tem µ menor) torna a transferência lateral um custo real.
- Curva: ay_max resolvido por eixo (o mais fraco limita) -> velocidade máx. por bissecção, sem velocidades impossíveis.
- Tração: min(força do motor+MGU-K via curva de potência/marcha, aderência do eixo traseiro pelo círculo de atrito).
- Frenagem: aderência dos dois eixos (círculo de atrito) com balanço de freio e capacidade do sistema.
- Passe regressivo (frenagem) + progressivo (aceleração) partindo do ponto de menor velocidade -> volta periódica.
- Pneus: temperatura (dinâmica 1ª ordem), desgaste e degradação realimentam a aderência (iteração).
- ERS: energia de entrega limitada pela recuperação real em frenagem (+ MGU-H quando existir) e tetos regulamentares.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import tires as T
from .circuits import Track
from .config import CarConfig, Environment
from .regulations import Season

G = 9.80665
LHV = 42.5e6        # J/kg (estimado)
V_CAP = 118.0       # m/s, teto numérico das velocidades-limite
LAT_USE = 0.965     # fração da velocidade-limite de curva usada (reserva de aderência p/ vencer arrasto)


def air_density(temp_c: float, altitude_m: float) -> float:
    p = 101325.0 * (1 - 2.25577e-5 * altitude_m) ** 5.25588
    return p / (287.05 * (temp_c + 273.15))


@dataclass
class LapResult:
    lap_time: float
    car: CarConfig
    env: Environment
    track: Track
    compound: str
    wear_start: float
    wear_end: float
    fuel_kg: float
    fuel_used_kg: float
    tel: dict                      # arrays por ponto
    sectors: list                  # tempos por setor
    segments: list                 # dicts por segmento
    braking_zones: list
    summary: dict
    violations: list = field(default_factory=list)
    compliant: bool = True
    converged: bool = True

    def fmt_time(self) -> str:
        return format_time(self.lap_time)


def format_time(t: float) -> str:
    m = int(t // 60)
    return f"{m}:{t - 60 * m:06.3f}"


class LapSimulator:
    def __init__(self, track: Track, car: CarConfig, env: Environment | None = None,
                 season: Season | None = None, ds: float = 6.0):
        self.track, self.car, self.env, self.season = track, car, env or Environment(), season
        d = track.discretize(ds)
        self.d = d
        self.n, self.ds = d["n"], d["ds"]
        self.s = d["s"]
        self.kappa = d["kappa"]
        self.absk = np.abs(self.kappa)
        self.seg_id = d["seg_id"]
        self.rho = air_density(self.env.air_temp_c, track.altitude_m)
        self.dens_pw = (self.rho / 1.225) ** 0.35        # perda de potência por altitude (turbo compensa parte)
        self.t_env = T.t_env(self.env.air_temp_c, self.env.track_temp_c)
        # modo reta (DRS 2025 / aero ativa 2026)
        sm = season.value("straight_mode") if season else None
        self.sm = sm
        elig = np.zeros(self.n, bool)
        if sm:
            for k, sg in enumerate(track.segments):
                if sg.kind == "straight" and sg.length >= sm["min_straight_m"]:
                    m = self.seg_id == k
                    # só no miolo da reta (fecha antes da zona de frenagem)
                    elig |= m & (self.s > sg.s0 + 0.04 * sg.length)
        self.elig = elig
        self.ratios = [r * car.final_drive for r in car.gear_ratios]
        self.ng = len(self.ratios)

    # ------------------------------------------------------------------ propriedades por ponto
    def _aero(self, i, v, closed=False):
        c = self.car
        cda, cla = c.cda, c.cla
        if (not closed) and self.sm and self.elig[i]:
            cda *= self.sm["cd_factor"]; cla *= self.sm["cl_factor"]
        q = 0.5 * self.rho * v * v
        return q * cda, q * cla     # (arrasto N, downforce N) com v relativo ao ar tratado fora

    # ------------------------------------------------------------------ limites de curva (vetorizado)
    def _corner_limits(self, mass, fTf, fTr, K):
        c, comp = self.car, self.comp
        absk = self.absk
        v = np.full(self.n, 60.0)
        lo = np.full(self.n, 3.0)
        hi = np.full(self.n, V_CAP)
        W = mass * G
        wf, h, tw, rsf = c.front_weight_frac, c.cog_height_m, c.track_width_m, c.roll_stiffness_front
        mu0, ks = comp.mu0_dry * K, comp.load_sens

        def tf(Fz, fT):
            load = np.clip(1.0 - ks * (Fz / T.FZ_REF - 1.0), 0.35, 1.3)
            return mu0 * fT * load * Fz

        def amax(vv):
            DF = 0.5 * self.rho * c.cla * vv * vv
            Fzf, Fzr = wf * W + c.aero_front_frac * DF, (1 - wf) * W + (1 - c.aero_front_frac) * DF
            a = np.full_like(vv, 25.0)
            for _ in range(6):
                llt = mass * a * h / tw
                df, dr = llt * rsf, llt * (1 - rsf)
                Ff = tf(Fzf * 0.5 + df, fTf) + tf(np.maximum(Fzf * 0.5 - df, 0.05 * Fzf), fTf)
                Fr = tf(Fzr * 0.5 + dr, fTr) + tf(np.maximum(Fzr * 0.5 - dr, 0.05 * Fzr), fTr)
                an = np.minimum(Ff / (wf * mass), Fr / ((1 - wf) * mass))
                a = 0.5 * a + 0.5 * an
            return a

        corner = absk > 1e-5
        for _ in range(26):
            mid = 0.5 * (lo + hi)
            ok = amax(mid) >= mid * mid * absk
            lo = np.where(ok, mid, lo)
            hi = np.where(ok, hi, mid)
        vc = np.where(corner, lo, V_CAP)
        return np.minimum(vc * LAT_USE, V_CAP)

    # ------------------------------------------------------------------ simulação
    def _pass(self, mass, Tf, Tr, K, ers_scale, budget_j):
        comp = self.comp
        fTf, fTr = T.f_temp(comp, Tf), T.f_temp(comp, Tr)
        v_lim = self._corner_limits(mass, fTf, fTr, K)
        i0 = int(np.argmin(v_lim))
        rot = lambda a: np.roll(a, -i0)
        vb = self._backward(rot(v_lim), mass, rot(fTf), rot(fTr), K, rot(self.kappa))
        vf, e_req = self._forward(vb, mass, rot(fTf), rot(fTr), K, rot(self.kappa), rot(self.elig),
                                  ers_scale, budget_j)
        v = np.roll(vf, i0)
        tel = self._telemetry(v, mass, fTf, fTr, K)
        return tel, e_req

    def _ers_update(self, tel, e_req):
        c = self.car
        harvest = min(tel["harvest_j"], c.harvest_cap_mj * 1e6)
        budget = min(c.deploy_cap_mj * 1e6, harvest * c.ers_roundtrip_eff + c.mguh_extra_mj * 1e6)
        if c.ers_strategy == "greedy":
            return 1.0, budget
        return (min(1.0, budget / e_req) if e_req > 0 else 1.0), None

    def run(self, wear: float = 0.0, fuel_kg: float | None = None, t_init: float | None = None,
            n_outer: int = 2, wear_max_hint: float = 1.5) -> LapResult:
        """Simula uma volta.

        Estratégia de iteração (determinística, sem realimentação instável):
          1) volta de referência com pneus na janela ideal (e ERS iterado) -> carregamentos por ponto;
          2) temperatura dos pneus ao longo da volta a partir desses carregamentos (periódica em volta
             rápida, ou partindo de ``t_init`` para volta fria/out-lap);
          3) volta final com a aderência dependente da temperatura (e ERS reiterado).
        """
        c, env, tr = self.car, self.env, self.track
        self.comp = comp = T.get_compound(c.compound)
        fuel = c.fuel_start_kg if fuel_kg is None else fuel_kg
        mass = c.mass_kg + fuel
        K = float(T.f_wear(comp, wear) * T.f_wet(comp, env.wetness) * tr.asphalt_grip)
        Tf = np.full(self.n, comp.t_opt - 2.0)
        Tr = Tf.copy()
        ers_scale, budget_j = 1.0, None
        for _ in range(n_outer):
            tel, e_req = self._pass(mass, Tf, Tr, K, ers_scale, budget_j)
            ers_scale, budget_j = self._ers_update(tel, e_req)
        Tf, Tr = self._thermal(tel, comp, t_init)
        lt_prev = float(tel["dt"].sum())
        converged = False
        for _ in range(n_outer):
            tel, e_req = self._pass(mass, Tf, Tr, K, ers_scale, budget_j)
            ers_scale, budget_j = self._ers_update(tel, e_req)
            lt = float(tel["dt"].sum())
            converged = abs(lt - lt_prev) < 0.05
            lt_prev = lt
        tel["Tf"], tel["Tr"] = Tf, Tr
        wear_inc = self._wear(tel, comp, env, tr)
        return self._pack(tel, mass, fuel, wear, wear_inc, converged)

    # ------------------------------------------------------------------ passe regressivo
    def _backward(self, vl, mass, fTf, fTr, K, kap):
        c, comp = self.car, self.comp
        n, ds = self.n, self.ds
        W = mass * G
        wf, af, h, L, tw, rsf = c.front_weight_frac, c.aero_front_frac, c.cog_height_m, c.wheelbase_m, c.track_width_m, c.roll_stiffness_front
        mu0, ks = comp.mu0_dry * K, comp.load_sens
        rho, cda, cla, crr = self.rho, c.cda, c.cla, c.crr
        vw = self.env.headwind_ms
        bias, maxg = c.brake_bias_front, c.max_brake_g
        vb = vl.copy()

        def tf(Fz, fT):
            load = 1.0 - ks * (Fz / T.FZ_REF - 1.0)
            load = 0.35 if load < 0.35 else (1.3 if load > 1.3 else load)
            return mu0 * fT * load * Fz

        for i in range(n - 1, 0, -1):
            vn = vb[(i + 1) % n]
            k = abs(kap[i])
            q = 0.5 * rho * vn * vn
            DF, D = q * cla, 0.5 * rho * cda * (vn + vw) ** 2
            Rr = crr * (W + DF)
            ay = vn * vn * k
            a = 4.0 * G
            fF, fR = fTf[i], fTr[i]
            for _ in range(3):
                dxl = mass * a * h / L
                Fzf = wf * W + af * DF + dxl
                Fzr = (1 - wf) * W + (1 - af) * DF - dxl
                llt = mass * ay * h / tw
                df, dr = llt * rsf, llt * (1 - rsf)
                Cf = tf(Fzf * 0.5 + df, fF) + tf(max(Fzf * 0.5 - df, 0.025 * Fzf), fF)
                Cr = tf(Fzr * 0.5 + dr, fR) + tf(max(Fzr * 0.5 - dr, 0.025 * Fzr), fR)
                yf, yr = wf * mass * ay, (1 - wf) * mass * ay
                xf = Cf * math.sqrt(max(1.0 - (yf / Cf) ** 2, 0.0)) if Cf > 1 else 0.0
                xr = Cr * math.sqrt(max(1.0 - (yr / Cr) ** 2, 0.0)) if Cr > 1 else 0.0
                Fb = min(xf / bias, xr / (1 - bias), maxg * W)
                a = 0.5 * a + 0.5 * ((Fb + D + Rr) / mass)
            v2 = vn * vn + 2.0 * a * ds
            vi = math.sqrt(v2)
            if vi < vb[i]:
                vb[i] = vi
        return vb

    # ------------------------------------------------------------------ passe progressivo
    def _forward(self, vb, mass, fTf, fTr, K, kap, elig, ers_scale, budget_j):
        c, comp = self.car, self.comp
        n, ds = self.n, self.ds
        W = mass * G
        wf, af, h, L, tw, rsf = c.front_weight_frac, c.aero_front_frac, c.cog_height_m, c.wheelbase_m, c.track_width_m, c.roll_stiffness_front
        mu0, ks = comp.mu0_dry * K, comp.load_sens
        rho, crr, eta = self.rho, c.crr, c.drivetrain_eff
        vw = self.env.headwind_ms
        sm = self.sm
        pk_full = c.mguk_kw * 1e3
        pmax, peak, red = c.ice_pmax_kw * 1e3 * self.dens_pw, c.ice_peak_rpm, c.redline_rpm
        rw = c.wheel_radius_m
        ratios, ng = self.ratios, self.ng
        rpm_k = 60.0 / (2 * math.pi * rw)
        v = vb[0]
        vf = vb.copy()
        vf[0] = v
        # marcha inicial
        g = ng - 1
        for gi in range(ng):
            if v * rpm_k * ratios[gi] < c.shift_rpm:
                g = gi
                break
        dead = 0.0
        e_req = 0.0
        e_used = 0.0
        a_prev = 0.0
        for i in range(n - 1):
            k = abs(kap[i])
            rpm = v * rpm_k * ratios[g]
            if rpm > c.shift_rpm and g < ng - 1:
                g += 1; rpm = v * rpm_k * ratios[g]; dead = c.shift_time_s
            elif rpm < c.downshift_rpm and g > 0:
                g -= 1; rpm = v * rpm_k * ratios[g]
            cda, cla = c.cda, c.cla
            if sm and elig[i]:
                cda *= sm["cd_factor"]; cla *= sm["cl_factor"]
            q = 0.5 * rho * v * v
            DF, D = q * cla, 0.5 * rho * cda * (v + vw) ** 2
            Rr = crr * (W + DF)
            # motor
            if rpm >= red:
                P_ice = 0.0
            else:
                x = max(rpm, 4500.0) / peak
                P_ice = pmax * max(x + x * x - x * x * x, 0.1)
            # MGU-K
            full_thr_possible = v < vb[i + 1] - 1e-9 or True
            if budget_j is not None:
                pk = pk_full if e_used < budget_j else 0.0
            else:
                pk = pk_full * ers_scale
            vv = max(v, 15.0)
            F_eng = eta * (P_ice + pk) / vv if dead <= 0.0 else 0.0
            # aderência traseira
            ay = v * v * k
            dxl = mass * a_prev * h / L
            Fzr = (1 - wf) * W + (1 - af) * DF + max(dxl, 0.0)
            llt = mass * ay * h * (1 - rsf) / tw
            fT = fTr[i]
            o, inn = Fzr * 0.5 + llt, max(Fzr * 0.5 - llt, 0.025 * Fzr)
            def tf(Fz):
                load = 1.0 - ks * (Fz / T.FZ_REF - 1.0)
                load = 0.35 if load < 0.35 else (1.3 if load > 1.3 else load)
                return mu0 * fT * load * Fz
            Cr = tf(o) + tf(inn)
            yr = (1 - wf) * mass * ay
            xr = Cr * math.sqrt(max(1.0 - (yr / Cr) ** 2, 0.0)) if Cr > 1 else 0.0
            F_drive = F_eng if F_eng < xr else xr
            a = (F_drive - D - Rr) / mass
            a_prev = a
            v2 = v * v + 2.0 * a * ds
            vn = math.sqrt(v2) if v2 > 0.25 else 0.5
            lim = vb[i + 1]
            if vn < lim:
                if F_eng <= xr:   # potência limita (ERS em uso)
                    dtp = ds / max(v, 1.0)
                    e_req += pk_full * dtp if budget_j is None else (pk_full * dtp)
                    e_used += pk * dtp
                vf[i + 1] = vn
                v = vn
            else:
                vf[i + 1] = lim
                v = lim
            dead -= ds / max(v, 1.0)
        return vf, e_req

    # ------------------------------------------------------------------ telemetria completa
    def _telemetry(self, v, mass, fTf, fTr, K):
        c, comp, env = self.car, self.comp, self.env
        n, ds = self.n, self.ds
        W = mass * G
        wf, af, h, L, tw, rsf = c.front_weight_frac, c.aero_front_frac, c.cog_height_m, c.wheelbase_m, c.track_width_m, c.roll_stiffness_front
        mu0, ks = comp.mu0_dry * K, comp.load_sens
        rho, crr, eta = self.rho, c.crr, c.drivetrain_eff
        rw = c.wheel_radius_m
        rpm_k = 60.0 / (2 * math.pi * rw)
        ratios, ng = self.ratios, self.ng
        vn_ = np.roll(v, -1)
        ax = (vn_ ** 2 - v ** 2) / (2 * ds)
        vm = 0.5 * (v + vn_)
        dt = ds / np.maximum(vm, 1.0)
        out = {k: np.zeros(n) for k in ("rpm", "gear", "throttle", "brake", "drag", "downforce", "ay", "util_f", "util_r",
                                         "p_ice", "p_k", "p_harv", "fuel_rate", "aero_open", "f_drive", "f_brake", "wheel_p")}
        pmax, peak, red = c.ice_pmax_kw * 1e3 * self.dens_pw, c.ice_peak_rpm, c.redline_rpm
        pk_full = c.mguk_kw * 1e3
        sm = self.sm
        # marcha: duas varreduras para estabilizar o estado
        g = ng - 1
        for gi in range(ng):
            if v[0] * rpm_k * ratios[gi] < c.shift_rpm:
                g = gi; break
        for sweep in range(2):
            for i in range(n):
                vi = float(v[i])
                rpm = vi * rpm_k * ratios[g]
                if rpm > c.shift_rpm and g < ng - 1:
                    g += 1; rpm = vi * rpm_k * ratios[g]
                elif rpm < c.downshift_rpm and g > 0:
                    g -= 1; rpm = vi * rpm_k * ratios[g]
                if sweep == 1:
                    out["gear"][i] = g + 1
                    out["rpm"][i] = rpm
        harvest = 0.0
        fuel_total = 0.0
        for i in range(n):
            vi = float(v[i]); rpm = out["rpm"][i]
            k = abs(self.kappa[i])
            cda, cla = c.cda, c.cla
            open_ = bool(sm and self.elig[i] and ax[i] > -0.08 * G)
            if open_:
                cda *= sm["cd_factor"]; cla *= sm["cl_factor"]
            q = 0.5 * rho * vi * vi
            DF, D = q * cla, 0.5 * rho * cda * (vi + env.headwind_ms) ** 2
            Rr = crr * (W + DF)
            ay = vi * vi * k
            F_req = mass * ax[i] + D + Rr
            x = max(rpm, 4500.0) / peak
            P_ice_av = 0.0 if rpm >= red else pmax * max(x + x * x - x * x * x, 0.1)
            fF, fR = fTf[i], fTr[i]
            # capacidade dos eixos nesta condição
            dxl = mass * ax[i] * h / L
            Fzf = wf * W + af * DF - dxl
            Fzr = (1 - wf) * W + (1 - af) * DF + dxl
            llt = mass * ay * h / tw
            def axle(Fz, dF, fT):
                def tf(z):
                    load = min(max(1.0 - ks * (z / T.FZ_REF - 1.0), 0.35), 1.3)
                    return mu0 * fT * load * z
                return tf(Fz * 0.5 + dF) + tf(max(Fz * 0.5 - dF, 0.025 * Fz))
            Cf, Cr = axle(Fzf, llt * rsf, fF), axle(Fzr, llt * (1 - rsf), fR)
            Cf1, Cr1 = axle(Fzf, llt * rsf, 1.0), axle(Fzr, llt * (1 - rsf), 1.0)   # referência térmica: janela ideal
            yf, yr = wf * mass * ay, (1 - wf) * mass * ay
            Fx_f, Fx_r = 0.0, 0.0
            thr = brk = 0.0
            F_drive = F_brk = P_ice = P_k = P_h = 0.0
            if F_req > 0:
                avail = eta * (P_ice_av + pk_full) / max(vi, 15.0)
                thr = min(F_req / max(avail, 1.0), 1.0)
                F_drive = F_req
                P_wheel = F_drive * vi / eta
                P_k = min(pk_full, P_wheel) * 0.0
                Fx_r = F_drive
            else:
                F_brk = max(-F_req, 0.0)
                if F_brk > 0.02 * W:           # frenagem real; abaixo disso é desaceleração livre
                    xf = Cf * math.sqrt(max(1.0 - (yf / Cf) ** 2, 0.0)) if Cf > 1 else 1.0
                    xr = Cr * math.sqrt(max(1.0 - (yr / Cr) ** 2, 0.0)) if Cr > 1 else 1.0
                    cap = min(xf / c.brake_bias_front, xr / (1 - c.brake_bias_front), c.max_brake_g * W)
                    brk = min(F_brk / max(cap, 1.0), 1.0)
                    Fx_f, Fx_r = c.brake_bias_front * F_brk, (1 - c.brake_bias_front) * F_brk
                    P_h = min(pk_full, (1 - c.brake_bias_front) * F_brk * vi)
                    harvest += P_h * dt[i]
            # divisão de potência ICE / MGU-K (entrega proporcional ao uso)
            if F_drive > 0:
                P_wheel_req = F_drive * vi / eta
                # fração elétrica: usada onde o motor sozinho não basta (reta em plena carga)
                P_ice = min(P_wheel_req, P_ice_av)
                P_k = max(P_wheel_req - P_ice, 0.0)
                P_k = min(P_k, pk_full)
            fuel_rate = P_ice / (c.ice_thermal_eff * LHV) if P_ice > 0 else 0.0
            fuel_total += fuel_rate * dt[i]
            uf = math.hypot(yf, Fx_f) / max(Cf1, 1.0)
            ur = math.hypot(yr, Fx_r) / max(Cr1, 1.0)
            o = out
            o["throttle"][i], o["brake"][i] = thr, brk
            o["drag"][i], o["downforce"][i], o["ay"][i] = D, DF, ay
            o["util_f"][i], o["util_r"][i] = min(uf, 1.1), min(ur, 1.1)
            o["p_ice"][i], o["p_k"][i], o["p_harv"][i] = P_ice, P_k, P_h
            o["fuel_rate"][i], o["aero_open"][i] = fuel_rate, 1.0 if open_ else 0.0
            o["f_drive"][i], o["f_brake"][i], o["wheel_p"][i] = F_drive, F_brk, F_drive * vi
        # energia ERS entregue efetiva (limitada ao orçamento no pós-processamento)
        out.update(v=v, ax=ax, dt=dt, harvest_j=harvest, fuel_used=fuel_total)
        return out

    # ------------------------------------------------------------------ térmica
    def _thermal(self, tel, comp, t_init):
        n = self.n
        v, dt = tel["v"], tel["dt"]
        te = self.t_env
        gain = comp.heat_gain
        res = []
        for u in (tel["util_f"], tel["util_r"]):
            q = gain * (0.10 + u * u) * (np.maximum(v, 5.0) / 55.0) ** 0.9    # potência de escorregamento ~ u²·v^0.9
            tss = te + T.H_GAIN * q / T.cooling(v)
            alpha = 1.0 - np.exp(-dt / T.TAU_S)
            Tc = comp.t_opt - 4.0 if t_init is None else t_init
            laps = 3 if t_init is None else 1
            for lap in range(laps):
                arr = np.empty(n)
                for i in range(n):
                    Tc += (tss[i] - Tc) * alpha[i]
                    arr[i] = Tc
            res.append(arr)
        return res

    def _wear(self, tel, comp, env, tr):
        u = 0.5 * (tel["util_f"] + tel["util_r"])
        Tm = 0.5 * (tel["Tf"] + tel["Tr"])
        over = np.maximum(Tm - (comp.t_opt + 0.6 * comp.t_width), 0.0) / comp.t_width
        mult = 1.0 + comp.overheat_wear * over ** 2
        sev = np.clip(u, 0, 1.1) ** 2.2 / 0.30
        return float(np.sum(sev * mult * (self.ds / tr.length_m)) * tr.abrasiveness / comp.life_laps)

    # ------------------------------------------------------------------ resultados
    def _pack(self, tel, mass, fuel, wear0, wear_inc, converged) -> LapResult:
        c, tr, env = self.car, self.track, self.env
        n, ds = self.n, self.ds
        dt = tel["dt"]
        lt = float(dt.sum())
        t_cum = np.concatenate([[0], np.cumsum(dt)])[:-1]
        tel["t"] = t_cum
        tel["s"] = self.s
        tel["x"], tel["y"] = self.d["x"], self.d["y"]
        tel["heading"] = self.d["heading"]
        tel["kappa"] = self.kappa
        tel["seg_id"] = self.seg_id
        tel["v_kmh"] = tel["v"] * 3.6
        tel["ay_g"] = tel["ay"] / G
        tel["ax_g"] = tel["ax"] / G
        tel["Tm"] = 0.5 * (tel["Tf"] + tel["Tr"])
        tel["util"] = np.maximum(tel["util_f"], tel["util_r"])
        # setores
        b = tr.sector_bounds()
        sectors = []
        for k in range(3):
            m = (self.s >= b[k]) & (self.s < b[k + 1])
            sectors.append(float(dt[m].sum()))
        # segmentos
        segs = []
        for k, sg in enumerate(tr.segments):
            m = self.seg_id == k
            if not m.any():
                continue
            segs.append(dict(name=sg.name, kind=sg.kind, length=sg.length, time=float(dt[m].sum()),
                             v_min=float(tel["v"][m].min() * 3.6), v_max=float(tel["v"][m].max() * 3.6),
                             v_avg=float(sg.length / max(dt[m].sum(), 1e-9) * 3.6),
                             radius=sg.radius, ay_max=float(tel["ay"][m].max() / G)))
        # zonas de frenagem
        brk = tel["brake"] > 0.05
        zones, i = [], 0
        idx = np.flatnonzero(brk)
        if idx.size:
            groups = np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1)
            for gidx in groups:
                if gidx.size < 2:
                    continue
                a, b2 = gidx[0], gidx[-1]
                zones.append(dict(s_start=float(self.s[a]), distance=float((b2 - a + 1) * ds),
                                  v_in=float(tel["v"][a] * 3.6), v_out=float(tel["v"][min(b2 + 1, n - 1)] * 3.6),
                                  peak_g=float(-tel["ax"][a:b2 + 1].min() / G)))
        v = tel["v"]
        summary = dict(
            lap_time_s=lt, v_max_kmh=float(v.max() * 3.6), v_min_kmh=float(v.min() * 3.6),
            v_avg_kmh=float(tr.length_m / lt * 3.6),
            a_long_max_g=float(tel["ax"].max() / G), a_brake_max_g=float(-tel["ax"].min() / G),
            a_lat_max_g=float(tel["ay"].max() / G),
            downforce_max_kn=float(tel["downforce"].max() / 1e3),
            braking_distance_total_m=float(sum(z["distance"] for z in zones)),
            n_braking_zones=len(zones),
            fuel_used_kg=float(tel["fuel_used"]),
            harvest_mj=float(min(tel["harvest_j"], c.harvest_cap_mj * 1e6) / 1e6),
            ers_deploy_mj=float(np.sum(tel["p_k"] * dt) / 1e6),
            tyre_temp_mean_c=float(tel["Tm"].mean()), tyre_temp_min_c=float(tel["Tm"].min()),
            tyre_temp_max_c=float(tel["Tm"].max()),
            tyre_wear_per_lap=wear_inc, tyre_wear_end=wear0 + wear_inc,
            tyre_util_mean=float(tel["util"].mean()),
            time_corners_s=float(sum(s["time"] for s in segs if s["kind"] == "corner")),
            time_straights_s=float(sum(s["time"] for s in segs if s["kind"] == "straight")),
            air_density=self.rho, mass_kg=mass,
        )
        return LapResult(lt, c, env, tr, c.compound, wear0, wear0 + wear_inc, fuel, float(tel["fuel_used"]),
                         tel, sectors, segs, zones, summary, converged=converged)
