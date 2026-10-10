from PySide6.QtCore import Qt, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QPainter

ICON_PATHS = {
    "lasso":'<path d="M7 17c-8-2-6-14 7-13 14 1 8 13-2 14-9 1-9-5-5-5 7 0 5 10 0 10"/>',
    "transform":'<path d="M5 5h14v14H5Z"/><path d="M2 2h6v6H2Zm14 0h6v6h-6ZM2 16h6v6H2Zm14 0h6v6h-6Z"/>',
    'brush':'<path d="m10 14 9-11 3 3-11 9M10 14c-5-2-4 5-8 6 6 2 9-1 8-6Z"/>',
    'eraser':'<path d="m3 15 11-12 8 8-10 10H8Zm5 6h14M8 10l8 8"/>',
    'move':'<path d="M12 2v20M2 12h20M8 6l4-4 4 4M8 18l4 4 4-4M6 8l-4 4 4 4M18 8l4 4-4 4"/>',
    'select':'<path stroke-dasharray="3 3" d="M3 3h18v18H3Z"/>',
    'text':'<path d="M4 6V3h16v3M12 3v18M8 21h8"/>',
    'rectangle':'<rect x="3" y="4" width="18" height="16" rx="1"/>',
    'ellipse':'<ellipse cx="12" cy="12" rx="9" ry="8"/>',
    'pipette':'<path d="m15 3 6 6M17 5l-3 3M14 8 3 19v2h2L16 10"/>',
    'fill':'<path d="m6 3 12 12M5 7l6-5 10 10-10 9L2 12Zm-3 5h19M21 17c-5 5 2 5 0 0Z"/>',
    'crop':'<path d="M6 2v16h16M2 6h16v16M20 3 3 20"/>',

    'feather': '<path d="M20 3c-7-2-15 3-14 11l4 3c8 0 12-7 10-14Z"/><path d="M3 21 16 8M7 17h5M11 13h5"/>',
    'folder': '<path d="M3 6h6l2 2h10v12H3Z"/>',
    'save': '<path d="M4 3h13l3 3v15H4Z"/><path d="M8 3v6h8V3M8 21v-8h8v8"/>',
    'export': '<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',
    'moon': '<path d="M20 14A9 9 0 0 1 10 3a9 9 0 1 0 10 11Z"/>',
    'focus': '<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
    'plus': '<path d="M12 5v14M5 12h14"/>',
    'up': '<path d="m6 14 6-6 6 6"/>',
    'down': '<path d="m6 10 6 6 6-6"/>',
    'left': '<path d="M4 5h16M4 10h10M4 15h16M4 20h10"/>',
    'center': '<path d="M4 5h16M7 10h10M4 15h16M7 20h10"/>',
    'right': '<path d="M4 5h16M10 10h10M4 15h16M10 20h10"/>',
    'justify': '<path d="M4 5h16M4 10h16M4 15h16M4 20h16"/>',
    'bullets': '<path d="M9 6h12M9 12h12M9 18h12"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/>',
    'numbers': '<path d="M10 6h11M10 12h11M10 18h11M3 4h2v5M3 13q3-3 3 0l-3 4h3"/>',
    'image': '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="2"/><path d="m4 19 6-7 4 4 3-4 4 5"/>',
    'table': '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
    'link': '<path d="m9 15 6-6M8 16l-2 2a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0M16 8l2-2a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0" transform="translate(1 0) scale(.9)"/>',
    'color': '<path d="m5 17 7-14 7 14M8 12h8M4 21h16"/>',
}

def vector_icon(name, color='#6856b3'):
    from PySide6.QtSvg import QSvgRenderer
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{ICON_PATHS[name]}</g></svg>'
    pix = QPixmap(48,48); pix.fill(Qt.transparent)
    painter = QPainter(pix); QSvgRenderer(QByteArray(svg.encode())).render(painter); painter.end()
    return QIcon(pix)

