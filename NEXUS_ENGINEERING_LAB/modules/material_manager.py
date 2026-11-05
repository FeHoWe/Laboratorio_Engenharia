"""Biblioteca de materiais.

Regra do projeto: o NEXUS nunca atribui material sozinho. Um arquivo importado
não carrega densidade confiável, então a massa só é calculada depois que o
USUÁRIO escolhe um material para o componente.

Densidades de referência (valores nominais de manuais técnicos, em g/cm³). Ligas
reais variam; use "Material personalizado" quando precisar de um valor exato.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "materials.db"


@dataclass(frozen=True)
class Material:
    name: str
    density_g_cm3: float
    builtin: bool = True
    category: Optional[str] = None       # só materiais do banco SQL
    density_min: Optional[float] = None  # faixa publicada pela fonte (g/cm³)
    density_max: Optional[float] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    note: Optional[str] = None


_BUILTIN = [
    Material("Aço carbono", 7.85),
    Material("Aço inoxidável 304", 8.00),
    Material("Ferro fundido cinzento", 7.20),
    Material("Alumínio (liga genérica)", 2.70),
    Material("Latão", 8.50),
    Material("Bronze", 8.80),
    Material("Cobre", 8.96),
    Material("Titânio (Ti-6Al-4V)", 4.43),
    Material("ABS", 1.04),
    Material("Nylon (PA6)", 1.14),
    Material("Borracha (genérica)", 1.10),
]


class MaterialLibrary:
    """Materiais nativos + banco SQL de densidades (data/materials.db) + personalizados do projeto.

    Os 11 nativos sempre existem. O banco é opcional: se o arquivo não estiver presente,
    a biblioteca funciona só com os nativos (e avisa em `db_error`).
    """

    def __init__(self, db_path: Optional[Path] = DEFAULT_DB) -> None:
        self._materials: dict[str, Material] = {m.name: m for m in _BUILTIN}
        self.db_error: Optional[str] = None
        self.db_count = 0
        if db_path is not None:
            self._load_db(Path(db_path))

    def _load_db(self, path: Path) -> None:
        if not path.exists():
            self.db_error = f"Banco de materiais não encontrado: {path}"
            return
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                rows = con.execute(
                    "SELECT display_name, category, density_typ, density_min, density_max, "
                    "source_title, source_url, note FROM v_materials ORDER BY category, display_name"
                ).fetchall()
            finally:
                con.close()
        except sqlite3.Error as exc:
            self.db_error = f"Falha ao ler o banco de materiais: {exc}"
            return
        taken = {n.casefold() for n in self._materials}
        for name, cat, typ, lo, hi, st, su, note in rows:
            key = name.casefold()
            if key in taken:
                continue  # nome já usado (nativo ou entrada anterior) — mantém o primeiro
            taken.add(key)
            self._materials[name] = Material(name, float(typ), builtin=True, category=cat,
                                             density_min=lo, density_max=hi, source=st, source_url=su, note=note)
            self.db_count += 1

    def names(self) -> list[str]:
        return list(self._materials)

    def quick_names(self, current: Optional[str] = None) -> list[str]:
        """Lista curta para combos: nativos + personalizados (+ o atual, se vier do banco)."""
        base = [m.name for m in _BUILTIN] + [m.name for m in self.customs()]
        if current and current in self._materials and current not in base:
            base.append(current)
        return base

    def used_db_materials(self, names) -> list[Material]:
        """Materiais do banco SQL (não nativos, não personalizados) realmente atribuídos."""
        out, seen = [], set()
        for n in names:
            m = self._materials.get(n) if n else None
            if m and m.category and n not in seen:
                seen.add(n)
                out.append(m)
        return out

    def restore_snapshot(self, name: str, density_g_cm3: float) -> None:
        """Reabre um projeto: se o banco atual não tem o material, usa o valor salvo (como personalizado)."""
        if name not in self._materials:
            self._materials[name] = Material(name, float(density_g_cm3), builtin=False,
                                             note="Restaurado do arquivo do projeto (banco de materiais indisponível).")

    def categories(self) -> list[str]:
        return sorted({m.category for m in self._materials.values() if m.category})

    def by_category(self, category: str) -> list[Material]:
        return [m for m in self._materials.values() if m.category == category]

    def search(self, text: str) -> list[Material]:
        t = text.strip().casefold()
        return [m for m in self._materials.values() if t in m.name.casefold()]

    def get(self, name: Optional[str]) -> Optional[Material]:
        return self._materials.get(name) if name else None

    def add_custom(self, name: str, density_g_cm3: float) -> Material:
        name = name.strip()
        if not name:
            raise ValueError("O material precisa de um nome.")
        if density_g_cm3 <= 0:
            raise ValueError("A densidade deve ser maior que zero.")
        if name in self._materials and self._materials[name].builtin:
            raise ValueError(f"'{name}' é um material nativo e não pode ser sobrescrito.")
        mat = Material(name, float(density_g_cm3), builtin=False)
        self._materials[name] = mat
        return mat

    def customs(self) -> list[Material]:
        return [m for m in self._materials.values() if not m.builtin]

    @staticmethod
    def mass_g(volume_mm3: float, material: Material) -> float:
        """Massa em gramas. 1 cm³ = 1000 mm³."""
        return volume_mm3 / 1000.0 * material.density_g_cm3
