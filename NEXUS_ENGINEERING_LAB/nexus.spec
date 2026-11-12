# -*- mode: python ; coding: utf-8 -*-
# PyInstaller (modo pasta). NÃO TESTADO em Windows: gerado na V3.6 sem acesso a uma máquina Windows. Use tools\empacotar_windows.bat e leia o aviso.
from PyInstaller.utils.hooks import collect_all, collect_submodules
datas, binaries, hidden = [], [], []
for pkg in ("OCP", "vtkmodules", "gmsh", "PySide6"):
    try:
        d, b, h = collect_all(pkg); datas += d; binaries += b; hidden += h
    except Exception as e:                                   # pacote ausente: o build segue e o teste do .exe mostra o que faltou
        print("aviso: collect_all falhou para", pkg, e)
hidden += collect_submodules("modules") + collect_submodules("interface") + collect_submodules("core")
datas += [("assets", "assets"), ("samples", "samples"), ("data", "data")] if __import__("os").path.isdir("data") else [("assets", "assets"), ("samples", "samples")]
a = Analysis(["main/main.py"], pathex=["."], binaries=binaries, datas=datas, hiddenimports=hidden, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="NEXUS", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="NEXUS")
