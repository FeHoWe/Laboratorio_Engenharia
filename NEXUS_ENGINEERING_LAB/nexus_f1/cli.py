"""NEXUS F1 — linha de comando (mesmo núcleo da GUI).

Exemplos:
  python cli.py tracks
  python cli.py lap monza --compound soft --aero low_drag --fuel 10 --csv volta.csv --report volta.md
  python cli.py all --compound soft                     # tempo em todos os circuitos
  python cli.py compare silverstone --a low_drag:medium --b high_downforce:soft
  python cli.py tyres bahrain
  python cli.py strategy silverstone --laps 52 --max-stops 2
  python cli.py audio monza --out monza.wav [--mode onboard] [--profile v10_aspirado]
  python cli.py mobile monza spa monaco --out nexus_f1_mobile.html
"""
import argparse
import sys

from nexus_f1.core import circuits, regulations, report
from nexus_f1.core.api import simulate_lap
from nexus_f1.core.compare import compare_configs
from nexus_f1.core.config import Environment, default_car
from nexus_f1.core.laptime import format_time
from nexus_f1.core.regulations import RegulationError
from nexus_f1.core.strategy import StrategyModel, default_strategies


def build_car(a):
    car = default_car(a.season)
    car.mode = "experimental" if a.experimental else "regulatory"
    if a.aero:
        car.apply_aero_preset(a.aero)
    if a.compound:
        car.compound = a.compound
    if a.mass:
        car.mass_kg = a.mass
    return car


def env_of(a):
    return Environment(a.air, a.track_temp, a.wet)


def main(argv=None):
    p = argparse.ArgumentParser(description="NEXUS F1 Performance Simulator (CLI)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, track=True):
        if track:
            sp.add_argument("track", choices=circuits.list_circuits())
        sp.add_argument("--season", default="2025"); sp.add_argument("--compound"); sp.add_argument("--aero")
        sp.add_argument("--mass", type=float); sp.add_argument("--fuel", type=float, default=40.0)
        sp.add_argument("--air", type=float, default=25.0); sp.add_argument("--track-temp", type=float, default=38.0)
        sp.add_argument("--wet", type=float, default=0.0); sp.add_argument("--experimental", action="store_true")

    sub.add_parser("tracks")
    sp = sub.add_parser("lap"); common(sp); sp.add_argument("--csv"); sp.add_argument("--json"); sp.add_argument("--report")
    sp = sub.add_parser("all"); common(sp, False)
    sp = sub.add_parser("compare"); common(sp)
    for n in "abc": sp.add_argument(f"--{n}", help="aero:composto  (ex.: low_drag:medium)")
    sp = sub.add_parser("tyres"); common(sp)
    sp = sub.add_parser("strategy"); common(sp); sp.add_argument("--laps", type=int); sp.add_argument("--pit-loss", type=float)
    sp.add_argument("--max-stops", type=int, default=2)
    sp = sub.add_parser("audio"); common(sp); sp.add_argument("--out", default="volta.wav"); sp.add_argument("--mode", default="trackside")
    sp.add_argument("--profile", default="v6_turbo_hibrido")
    sp = sub.add_parser("mobile"); sp.add_argument("tracks", nargs="+"); sp.add_argument("--season", default="2025"); sp.add_argument("--out", default="nexus_f1_mobile.html")
    a = p.parse_args(argv)

    try:
        if a.cmd == "tracks":
            for k in circuits.list_circuits():
                c = circuits._C[k]; print(f"{k:11s} {c['name']:42s} {c['country']:16s} {c['length_m']} m  {c['turns']} curvas")
        elif a.cmd == "lap":
            r = simulate_lap(a.track, build_car(a), env_of(a), fuel_kg=a.fuel)
            print(report.lap_report_md(r))
            if a.csv: report.export_csv(r, a.csv)
            if a.json: report.export_json(r, a.json)
            if a.report: open(a.report, "w", encoding="utf-8").write(report.lap_report_md(r))
        elif a.cmd == "all":
            for k in circuits.list_circuits():
                r = simulate_lap(k, build_car(a), env_of(a), fuel_kg=a.fuel)
                print(f"{k:11s} {r.fmt_time()}  Vmax {r.summary['v_max_kmh']:.0f}  média {r.summary['v_avg_kmh']:.0f} km/h")
        elif a.cmd == "compare":
            cfgs = {}
            for n in "abc":
                v = getattr(a, n)
                if v:
                    aero, comp = v.split(":")
                    c = build_car(a).apply_aero_preset(aero); c.compound = comp; c.name = n.upper(); cfgs[n.upper()] = c
            print(report.comparison_report_md(compare_configs(a.track, cfgs, env_of(a), a.fuel)))
        elif a.cmd == "tyres":
            car = build_car(a)
            for comp in regulations.get_season(a.season).compounds["allowed"]:
                r = simulate_lap(a.track, car.copy(compound=comp), env_of(a), fuel_kg=a.fuel)
                s = r.summary
                print(f"{comp:13s} {r.fmt_time()}  T {s['tyre_temp_mean_c']:.0f} °C  desgaste/volta {s['tyre_wear_per_lap'] * 100:.2f}%")
        elif a.cmd == "strategy":
            sm = StrategyModel(a.track, build_car(a), env_of(a), pit_loss_s=a.pit_loss, race_laps=a.laps)
            print(report.strategy_report_md(sm.compare(default_strategies(sm)) + sm.optimize(max_stops=a.max_stops, top=5), sm.pit_loss))
        elif a.cmd == "audio":
            from nexus_f1.engine_audio import AudioSettings, SimulationAudio, write_wav
            r = simulate_lap(a.track, build_car(a), env_of(a), fuel_kg=a.fuel)
            k = int(r.tel["v"].argmax())
            st = AudioSettings(profile=a.profile, mode=a.mode, observer_s=float(r.tel["s"][k]))
            write_wav(a.out, SimulationAudio(r, st).render_all(), st.sr); print("áudio salvo em", a.out)
        elif a.cmd == "mobile":
            from nexus_f1.mobile.export import build_mobile_html
            car = default_car(a.season)
            res = [simulate_lap(t, car, fuel_kg=40) for t in a.tracks]
            open(a.out, "w", encoding="utf-8").write(build_mobile_html(res)); print("salvo em", a.out)
    except RegulationError as e:
        print("Configuração não regulamentar:", e, file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
