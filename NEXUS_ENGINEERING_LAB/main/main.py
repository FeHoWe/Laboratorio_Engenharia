"""Ponto de entrada do NEXUS ENGINEERING LAB.

Uso:  python main/main.py [arquivo.step|.stl|.obj|.FCStd|.nexus]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_config() -> dict:
    path = Path(__file__).with_name("config.json")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        from core.cad_engine import CadEngine, CadEngineError
        from interface.main_window import MainWindow
    except ImportError as exc:
        print(f"Dependência ausente: {exc}\nInstale com:  pip install -r requirements.txt", file=sys.stderr)
        return 2

    app = QApplication(sys.argv[:1])
    app.setApplicationName("NEXUS ENGINEERING LAB")
    try:
        engine = CadEngine()
    except CadEngineError as exc:
        QMessageBox.critical(None, "NEXUS — motor CAD indisponível", str(exc))
        return 3
    window = MainWindow(config=load_config(), engine=engine)
    window.show()
    if argv:
        target = argv[0]
        if target.lower().endswith(".nexus"):
            window.open_project(target)
        else:
            window.import_model(target)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
