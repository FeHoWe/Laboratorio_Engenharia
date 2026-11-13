# -*- mode: python ; coding: utf-8 -*-
# PyInstaller (modo pasta). NÃO TESTADO em Windows: gerado na V3.6 sem acesso a uma máquina Windows. Use tools\empacotar_windows.bat e leia o aviso.
# V110 (auditoria estática, também NÃO testada em Windows): faltavam `locales/` (traduções), `nexus_f1/data` e os pacotes importados só sob demanda (nexus_f1, ai, simulation).
from PyInstaller.utils.hooks import collect_all, collect_submodules
datas, binaries, hidden = [], [], []
for pkg in ("OCP", "vtkmodules", "gmsh", "PySide6"):
    try:
        d, b, h = collect_all(pkg); datas += d; binaries += b; hidden += h
    except Exception as e:                                   # pacote ausente: o build segue e o teste do .exe mostra o que faltou
        print("aviso: collect_all falhou para", pkg, e)
hidden += [m for pkg in ("modules", "interface", "core", "nexus_f1", "ai", "simulation", "samples") for m in collect_submodules(pkg)]
datas += [("assets", "assets"), ("samples", "samples"), ("data", "data")] if __import__("os").path.isdir("data") else [("assets", "assets"), ("samples", "samples")]
import os
for _pasta in ("locales", os.path.join("nexus_f1", "data")):
    if os.path.isdir(_pasta):
        datas.append((_pasta, _pasta))                       # lidos em tempo de execução (i18n e dados do simulador F1)
a = Analysis(["main/main.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hidden, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="NEXUS", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="NEXUS")
