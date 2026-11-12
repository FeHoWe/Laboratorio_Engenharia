"""Imagens offscreen (sem janela Qt) do modelo — usadas no relatório PDF.

Usa o mesmo SceneController da janela, mas num vtkRenderWindow offscreen próprio. Não mexe no
projeto: posições/visibilidade são aplicadas direto nos atores.
"""
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np
import vtkmodules.vtkInteractionStyle  # noqa: F401  (registra backends)
import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
from vtkmodules.vtkCommonCore import vtkUnsignedCharArray  # noqa: F401
from vtkmodules.vtkIOImage import vtkPNGWriter
from vtkmodules.vtkRenderingCore import vtkRenderWindow, vtkWindowToImageFilter

from core.component_manager import ComponentManager
from interface.viewport import SceneController


class SnapshotRenderer:
    def __init__(self, components: ComponentManager, holo: bool = True, jpeg: bool = True) -> None:
        self.jpeg = jpeg   # JPEG deixa o PDF leve (fundo escuro comprime bem)
        self.components = components
        self.scene = SceneController()
        self.scene.build(components)
        self.scene.set_holo(holo)
        self.scene.set_hud_visible(False)
        self.window = vtkRenderWindow()
        self.window.SetOffScreenRendering(1)
        self.window.AddRenderer(self.scene.renderer)

    @property
    def ok(self) -> bool:
        return bool(self.scene.parts)

    # ---------------------------------------------------------------- estado
    def _set_visible(self, ids: Optional[Iterable[str]]) -> None:
        keep = None if ids is None else set(ids)
        for cid, pa in self.scene.parts.items():
            v = keep is None or cid in keep
            pa.body.SetVisibility(v)
            pa.edges.SetVisibility(v and self.scene.edges_visible)

    def _reset(self) -> None:
        """Estado base: tudo visível, posição original, nada destacado, sem corte."""
        self._set_visible(None)
        self.scene.poses = {}
        for cid in self.scene.parts:
            self.scene.place(cid, (0, 0, 0))
        self.scene.set_highlight([])
        self.scene.set_section(None)

    def _grab(self, size: tuple[int, int]) -> bytes:
        self.window.SetSize(*size)
        self.window.Render()
        w2i = vtkWindowToImageFilter()
        w2i.SetInput(self.window)
        w2i.ReadFrontBufferOff()
        w2i.Update()
        writer = vtkPNGWriter()
        writer.WriteToMemoryOn()
        writer.SetInputConnection(w2i.GetOutputPort())
        writer.Write()
        png = bytes(memoryview(writer.GetResult()))
        if not self.jpeg:
            return png
        import io
        from PIL import Image
        buf = io.BytesIO()
        Image.open(io.BytesIO(png)).convert("RGB").save(buf, "JPEG", quality=85, optimize=True)
        return buf.getvalue()

    # ---------------------------------------------------------------- imagens
    def overview(self, size=(1100, 700), view: str = "iso") -> bytes:
        self._reset()
        self.scene.set_view(view)
        self.scene.renderer.GetActiveCamera().Zoom(1.25)
        return self._grab(size)

    def part(self, comp_id: str, size=(560, 400), view: str = "iso", context: bool = False) -> bytes:
        """A peça sozinha (enquadrada) ou, com context=True, destacada no conjunto."""
        self._reset()
        if comp_id not in self.scene.parts:
            raise KeyError(comp_id)
        self.scene.set_highlight([comp_id])
        self.scene.set_view(view)
        if context:
            self.scene.renderer.GetActiveCamera().Zoom(1.2)
        else:
            self._set_visible([comp_id])
            self.scene.fit_to([comp_id])
            self.scene.renderer.GetActiveCamera().Zoom(1.05)
        return self._grab(size)

    def saved_scene(self, sc, size=(1100, 700)) -> bytes:
        """Reproduz uma cena salva (câmera, explosão, visibilidade, corte, estilo)."""
        self._reset()
        self.scene.set_holo(sc.holo)
        self.scene.edges_visible = sc.edges
        hidden = set(sc.hidden)
        for n in self.components.root.walk():
            if n.id in hidden:
                for leaf in n.leaves() if not n.has_geometry else [n]:
                    pa = self.scene.parts.get(leaf.id)
                    if pa:
                        pa.body.SetVisibility(False)
                        pa.edges.SetVisibility(False)
        # offsets da cena: soma do próprio + ancestrais, usando os valores guardados
        stored = {k: np.asarray(v, dtype=float) for k, v in sc.offsets.items()}
        self.scene.poses = {k: np.asarray(v, dtype=float).reshape(4, 4) for k, v in (sc.poses or {}).items()}
        for leaf in self.components.leaves():
            pa = self.scene.parts.get(leaf.id)
            if pa is None:
                continue
            off = stored.get(leaf.id, np.zeros(3)).copy()
            for a in leaf.ancestors():
                off = off + stored.get(a.id, np.zeros(3))
            self.scene.place(leaf.id, off)
        if sc.section:
            rng = self.scene.section_range(int(sc.section["axis"]))
            if rng:
                pos = rng[0] + (rng[1] - rng[0]) * float(sc.section["fraction"])
                self.scene.set_section(int(sc.section["axis"]), pos, bool(sc.section.get("flip", False)))
        cam = self.scene.renderer.GetActiveCamera()
        c = sc.camera
        if c:
            cam.SetParallelProjection(bool(c.get("parallel", False)))
            cam.SetPosition(*c["position"])
            cam.SetFocalPoint(*c["focal"])
            cam.SetViewUp(*c["up"])
            if c.get("parallel"):
                cam.SetParallelScale(float(c["scale"]))
            self.scene.renderer.ResetCameraClippingRange()
        else:
            self.scene.set_view("iso")
        img = self._grab(size)
        self.scene.edges_visible = True
        self.scene.set_holo(True)
        return img
