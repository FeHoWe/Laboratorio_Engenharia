"""Identidade visual do NEXUS: tema escuro (preto, grafite, azul tecnológico).

Prioridade: funcionalidade. Sem efeitos decorativos; hierarquia por contraste e
um único acento (azul). Os ícones são desenhados em código (vetoriais), então
não há arquivos de imagem para distribuir nem perder.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

# --------------------------------------------------------------------- paleta
BG = "#070b11"
PANEL = "#0b1119"
PANEL_ALT = "#101a26"
BORDER = "#16384c"
TEXT = "#cfe9f5"
MUTED = "#6f95a8"
ACCENT = "#27d3ff"
ACCENT_DIM = "#136f8c"
OK = "#3fcf8e"
WARN = "#f2b84b"
ERROR = "#ff5d6c"

VIEWPORT_TOP = (0.020, 0.075, 0.115)
VIEWPORT_BOTTOM = (0.004, 0.012, 0.022)

# holograma (estilo bancada): ciano translúcido, seleção âmbar
HOLO_COLOR = (0.16, 0.72, 0.95)
HOLO_EDGE = (0.55, 0.96, 1.0)
HOLO_SELECTION = (1.0, 0.70, 0.18)
HOLO_GRID = (0.10, 0.52, 0.70)
HUD_COLOR = (0.35, 0.88, 1.0)

# tons técnicos (grafite/aço) usados ciclicamente nas peças — sem cores berrantes
PART_COLORS = [
    (0.58, 0.64, 0.72), (0.50, 0.58, 0.68), (0.66, 0.68, 0.72), (0.46, 0.52, 0.60),
    (0.62, 0.60, 0.56), (0.52, 0.62, 0.64), (0.60, 0.56, 0.66), (0.56, 0.60, 0.52),
]
SELECTION_COLOR = (0.18, 0.66, 1.0)

FONT_UI = '"Segoe UI", "Inter", "Roboto", "Helvetica Neue", Arial, sans-serif'
FONT_MONO = '"Cascadia Mono", "Consolas", "DejaVu Sans Mono", monospace'


def stylesheet() -> str:
    return f"""
* {{ font-family: {FONT_UI}; font-size: 12px; color: {TEXT}; }}
QMainWindow, QDialog {{ background: {BG}; }}
QWidget {{ background: transparent; }}
QMainWindow > QWidget {{ background: {BG}; }}
QToolTip {{ background: {PANEL_ALT}; color: {TEXT}; border: 1px solid {ACCENT_DIM}; padding: 4px; }}

QMenuBar {{ background: {PANEL}; border-bottom: 1px solid {BORDER}; padding: 2px; }}
QMenuBar::item {{ padding: 5px 10px; border-radius: 3px; }}
QMenuBar::item:selected {{ background: {PANEL_ALT}; color: {ACCENT}; }}
QMenu {{ background: {PANEL}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 6px 28px 6px 24px; border-radius: 3px; }}
QMenu::item:selected {{ background: {ACCENT_DIM}; color: white; }}
QMenu::item:disabled {{ color: {MUTED}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}

QToolBar {{ background: {PANEL}; border: none; border-bottom: 1px solid {BORDER}; spacing: 4px; padding: 3px 6px; }}
QToolBar::separator {{ width: 1px; background: {BORDER}; margin: 4px 6px; }}
QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 4px 6px; }}
QToolButton:hover {{ background: {PANEL_ALT}; border-color: {BORDER}; }}
QToolButton:checked {{ background: {ACCENT_DIM}; border-color: {ACCENT}; }}
QToolButton:disabled {{ color: {MUTED}; }}

QDockWidget {{ titlebar-close-icon: none; titlebar-normal-icon: none; }}
QDockWidget::title {{ background: {PANEL}; padding: 6px 10px; border-bottom: 2px solid {ACCENT_DIM};
    text-transform: uppercase; font-weight: 600; color: {MUTED}; }}
QMainWindow::separator {{ background: {BG}; width: 3px; height: 3px; }}

QTabWidget::pane {{ border: 1px solid {BORDER}; background: {PANEL}; top: -1px; }}
QTabBar::tab {{ background: {BG}; border: 1px solid {BORDER}; padding: 5px 12px; margin-right: 2px; color: {MUTED}; }}
QTabBar::tab:selected {{ background: {PANEL}; color: {ACCENT}; border-bottom-color: {PANEL}; }}

QTreeWidget, QListWidget, QTableWidget {{ background: {PANEL}; border: 1px solid {BORDER};
    alternate-background-color: {PANEL_ALT}; outline: 0; }}
QTreeWidget::item, QListWidget::item {{ padding: 3px 2px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{ background: {ACCENT_DIM}; color: white; }}
QTreeWidget::item:hover:!selected, QListWidget::item:hover:!selected {{ background: {PANEL_ALT}; }}
QHeaderView::section {{ background: {PANEL_ALT}; border: none; border-right: 1px solid {BORDER}; padding: 4px; color: {MUTED}; }}

QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 3px;
    padding: 4px 6px; selection-background-color: {ACCENT_DIM}; }}
QLineEdit:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QLineEdit:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{ color: {MUTED}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{ background: {PANEL}; border: 1px solid {BORDER}; selection-background-color: {ACCENT_DIM}; }}

QPushButton {{ background: {PANEL_ALT}; border: 1px solid {BORDER}; border-radius: 4px; padding: 6px 12px; }}
QPushButton:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
QPushButton:pressed {{ background: {ACCENT_DIM}; color: white; }}
QPushButton:disabled {{ color: {MUTED}; border-color: {PANEL_ALT}; }}
QPushButton#primary {{ background: {ACCENT_DIM}; border-color: {ACCENT}; color: white; }}

QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {BORDER}; border-radius: 3px; background: {BG}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QTreeView::indicator {{ width: 14px; height: 14px; border: 1px solid {MUTED}; border-radius: 3px; background: {BG}; }}
QTreeView::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QTreeView::indicator:indeterminate {{ background: {ACCENT_DIM}; border-color: {ACCENT_DIM}; }}
QListView::indicator {{ width: 14px; height: 14px; border: 1px solid {MUTED}; border-radius: 3px; background: {BG}; }}
QListView::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT_DIM}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ACCENT}; width: 12px; margin: -5px 0; border-radius: 6px; }}

QGroupBox {{ border: 1px solid {BORDER}; border-radius: 4px; margin-top: 14px; padding: 10px 8px 6px 8px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; color: {ACCENT}; font-weight: 600; }}

QPlainTextEdit, QTextEdit {{ background: {BG}; border: 1px solid {BORDER}; font-family: {FONT_MONO}; font-size: 11px; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: {BG}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT_DIM}; }}
QScrollBar:horizontal {{ background: {BG}; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 5px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QStatusBar {{ background: {PANEL}; border-top: 1px solid {BORDER}; }}
QStatusBar::item {{ border: none; }}
QProgressBar {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 3px; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT_DIM}; }}
QMessageBox {{ background: {PANEL}; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#section {{ color: {ACCENT}; font-weight: 600; }}
"""


# --------------------------------------------------------------------- ícones
def _pen(color: str, width: float = 1.7) -> QPen:
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


def _poly(p: QPainter, pts, close=False) -> None:
    path = QPainterPath(QPointF(*pts[0]))
    for x, y in pts[1:]:
        path.lineTo(x, y)
    if close:
        path.closeSubpath()
    p.drawPath(path)


def _cube(p: QPainter, fill: str | None = None, color: str = ACCENT) -> None:
    """Cubo isométrico em grade 24x24; ``fill`` pinta uma face (top|front|right)."""
    top = [(12, 3), (20, 7.5), (12, 12), (4, 7.5)]
    left = [(4, 7.5), (12, 12), (12, 21), (4, 16.5)]
    right = [(12, 12), (20, 7.5), (20, 16.5), (12, 21)]
    faces = {"top": top, "front": left, "right": right}
    if fill:
        p.setBrush(QColor(color))
        p.setOpacity(0.55)
        p.setPen(Qt.NoPen)
        path = QPainterPath(QPointF(*faces[fill][0]))
        for pt in faces[fill][1:]:
            path.lineTo(*pt)
        path.closeSubpath()
        p.drawPath(path)
        p.setOpacity(1.0)
        p.setBrush(Qt.NoBrush)
    p.setPen(_pen(color))
    for face in (top, left, right):
        _poly(p, face, close=True)


def _arrows(p: QPainter, outward: bool) -> None:
    """Quadrado central com 4 setas diagonais (para fora = explodir, para dentro = restaurar)."""
    p.setPen(_pen(ACCENT))
    p.drawRect(QRectF(9.5, 9.5, 5, 5))
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        near = QPointF(12 + dx * 6.0, 12 + dy * 6.0)
        far = QPointF(12 + dx * 10.0, 12 + dy * 10.0)
        start, tip = (near, far) if outward else (far, near)
        p.drawLine(start, tip)
        back = -1 if outward else 1          # a ponta aponta no sentido do movimento
        p.drawLine(tip, QPointF(tip.x() + back * dx * 2.4, tip.y()))
        p.drawLine(tip, QPointF(tip.x(), tip.y() + back * dy * 2.4))


def make_icon(name: str, color: str = ACCENT, size: int = 22) -> QIcon:
    """Ícone vetorial pelo nome. Desconhecido -> quadrado simples."""
    scale = 4
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(size * scale / 24.0, size * scale / 24.0)
    p.setPen(_pen(color))
    p.setBrush(Qt.NoBrush)

    if name == "open":
        _poly(p, [(3, 7), (3, 19), (20, 19), (20, 9), (11, 9), (9, 6), (3, 6), (3, 7)])
    elif name == "save":
        _poly(p, [(4, 4), (17, 4), (20, 7), (20, 20), (4, 20)], close=True)
        p.drawRect(QRectF(8, 4, 7, 5))
        p.drawRect(QRectF(7, 13, 10, 7))
    elif name == "import":
        _poly(p, [(12, 3), (12, 15)])
        _poly(p, [(7, 11), (12, 16), (17, 11)])
        _poly(p, [(4, 19), (20, 19)])
    elif name == "fit":
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            cx, cy = 12 + sx * 8, 12 + sy * 8
            _poly(p, [(cx - sx * 4, cy), (cx, cy), (cx, cy - sy * 4)])
        p.drawRect(QRectF(9, 9, 6, 6))
    elif name in ("view_front", "view_top", "view_right"):
        _cube(p, fill={"view_front": "front", "view_top": "top", "view_right": "right"}[name], color=color)
    elif name == "view_iso":
        _cube(p, color=color)
    elif name == "perspective":
        _poly(p, [(3, 8), (21, 4), (21, 20), (3, 16)], close=True)
        _poly(p, [(8, 9), (15, 7.8), (15, 16.2), (8, 15)], close=True)
    elif name == "ortho":
        p.drawRect(QRectF(4, 5, 16, 14))
        p.drawRect(QRectF(8, 9, 8, 6))
    elif name == "explode":
        _arrows(p, outward=True)
    elif name == "restore":
        _arrows(p, outward=False)
    elif name == "separate":
        p.drawRect(QRectF(3, 13, 8, 8))
        p.drawRect(QRectF(5, 15, 4, 4))
        p.drawRect(QRectF(13, 3, 8, 8))
        _poly(p, [(11, 12), (13, 10)])
    elif name == "group_explode":
        p.drawRect(QRectF(3, 3, 18, 18))
        p.drawRect(QRectF(6, 6, 5, 5))
        p.drawRect(QRectF(13, 13, 5, 5))
        _poly(p, [(11.5, 11.5), (13, 13)])
    elif name == "eye":
        path = QPainterPath(QPointF(2, 12))
        path.quadTo(12, 3, 22, 12)
        path.quadTo(12, 21, 2, 12)
        p.drawPath(path)
        p.drawEllipse(QPointF(12, 12), 3, 3)
    elif name == "isolate":
        p.drawRect(QRectF(7, 7, 10, 10))
        p.setPen(QPen(QColor(color), 1.4, Qt.DashLine))
        p.drawRect(QRectF(3, 3, 18, 18))
    elif name == "part":
        _cube(p, color=color)
    elif name == "assembly":
        p.drawRect(QRectF(3, 13, 8, 8))
        p.drawRect(QRectF(13, 13, 8, 8))
        p.drawRect(QRectF(8, 3, 8, 8))
    elif name == "group":
        _poly(p, [(3, 6), (3, 19), (21, 19), (21, 8), (11, 8), (9, 5), (3, 5), (3, 6)])
    elif name == "inspect":
        p.drawEllipse(QPointF(10.5, 10.5), 6, 6)
        _poly(p, [(15, 15), (21, 21)])
    else:
        p.drawRect(QRectF(5, 5, 14, 14))
    p.end()
    pm.setDevicePixelRatio(1.0)
    return QIcon(pm.scaled(size * 2, size * 2, Qt.KeepAspectRatio, Qt.SmoothTransformation))
