import sys
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QSize, QSettings, QStandardPaths
from PySide6.QtGui import (QAction, QActionGroup, QKeySequence, QPainter, QColor, QPen, QPainterPath,
    QFont, QImage, QTransform, QPixmap, QIcon, QPalette)
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QScrollArea,QToolBar,
    QDockWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QToolButton,QListWidget,
    QListWidgetItem,QSpinBox,QComboBox,QFontComboBox,QFileDialog,QMessageBox,
    QInputDialog,QSizePolicy,QTabBar,QCheckBox,QDialog,QDialogButtonBox,QFormLayout,QColorDialog)
from model import Project,Layer,blank,load_image,MODES,check_size

from icons import vector_icon

APP='Atelier'


class Canvas(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.zoom=1;self.selection=None;self.start=None;self.last=None;self.dragging=False
        self.setMouseTracking(True);self.setFocusPolicy(Qt.StrongFocus);self.space=False;self.pan_start=None;self.transform_corner=None
    def sync(self):
        p=self.window.project;self.setFixedSize(round(p.width*self.zoom)+64,round(p.height*self.zoom)+64);self.update()
    def point(self,event):return QPoint(int((event.position().x()-32)/self.zoom),int((event.position().y()-32)/self.zoom))
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.translate(32,32);p.scale(self.zoom,self.zoom)
        doc=self.window.project;p.fillRect(0,0,doc.width,doc.height,QColor('#ffffff'))
        p.save();p.setClipRect(0,0,doc.width,doc.height)
        for y in range(0,doc.height,20):
            for x in range(0,doc.width,20):
                if (x//20+y//20)%2==0:p.fillRect(x,y,20,20,QColor('#e3e5ec'))
        p.drawImage(0,0,doc.composite());p.restore()
        pen=QPen(QColor('#a99af2'),1/self.zoom,Qt.DashLine);p.setPen(pen);p.setBrush(Qt.NoBrush)
        if self.selection:
            p.drawPath(self.selection) if isinstance(self.selection,QPainterPath) else p.drawRect(self.selection)
        if self.window.tool=='Transformer':
            l=doc.layer;rect=QRect(l.x,l.y,l.image.width(),l.image.height());p.drawRect(rect);p.setBrush(QColor('#ddd5ff'))
            for pt in (rect.topLeft(),rect.topRight(),rect.bottomLeft(),rect.bottomRight()):
                size=8/self.zoom;p.drawRect(pt.x()-size/2,pt.y()-size/2,size,size)
        if self.dragging and self.window.tool in ('Rectangle','Ellipse'):
            r=QRect(self.start,self.last).normalized();p.setPen(QPen(self.window.color,2/self.zoom));p.drawEllipse(r) if self.window.tool=='Ellipse' else p.drawRect(r)
        p.end()
    def mousePressEvent(self,event):
        if event.button()==Qt.MiddleButton or (event.button()==Qt.LeftButton and self.space):
            self.pan_start=event.globalPosition().toPoint();self.pan_scroll=QPoint(self.window.scroll.horizontalScrollBar().value(),self.window.scroll.verticalScrollBar().value());self.setCursor(Qt.ClosedHandCursor);return
        if event.button()!=Qt.LeftButton:return
        self.setFocus();pt=self.point(event);w=self.window;doc=w.project
        if w.tool=='Transformer' and not doc.layer.locked:
            rect=QRect(doc.layer.x,doc.layer.y,doc.layer.image.width(),doc.layer.image.height())
            corners=[rect.topLeft(),rect.topRight(),rect.bottomLeft(),rect.bottomRight()]
            for i,corner in enumerate(corners):
                if (corner-pt).manhattanLength()<16/self.zoom:
                    if not w.ensure_pixels():return
                    self.transform_corner=i;self.transform_source=doc.layer.copy();self.transform_state=doc.state();self.transform_anchor=corners[3-i];self.dragging=True;self.start=self.last=pt;return
        if w.tool not in ('Sélection','Lasso','Recadrer','Pipette') and doc.layer.locked:
            w.statusBar().showMessage('Ce calque est verrouillé.',4000);return
        if not QRect(0,0,doc.width,doc.height).contains(pt):return
        if w.tool=='Pipette':w.set_color(doc.composite().pixelColor(pt));return
        if w.tool=='Texte':w.add_text(pt);return
        if w.tool=='Remplir':w.fill();return
        self.dragging=True;self.start=self.last=pt
        if w.tool in ('Sélection','Recadrer'):
            self.selection=QRect(pt,pt)
        elif w.tool=='Lasso':
            self.selection=QPainterPath();self.selection.moveTo(pt)
        else:
            if w.tool in ('Pinceau','Gomme','Rectangle','Ellipse') and not w.ensure_pixels():self.dragging=False;return
            doc.checkpoint(w.tool)
            if w.tool in ('Pinceau','Gomme'):doc.stroke(pt,pt,w.color,w.brush_size.value(),w.tool=='Gomme',self.selection,w.mask_edit)
            if w.tool in ('Déplacer','Transformer'):self.origin=QPoint(doc.layer.x,doc.layer.y)
            w.modified()
        self.update()
    def mouseMoveEvent(self,event):
        if self.pan_start is not None:
            delta=event.globalPosition().toPoint()-self.pan_start
            self.window.scroll.horizontalScrollBar().setValue(self.pan_scroll.x()-delta.x());self.window.scroll.verticalScrollBar().setValue(self.pan_scroll.y()-delta.y());return
        if not self.dragging:return
        pt=self.point(event);w=self.window;doc=w.project
        if self.transform_corner is not None:
            anchor=self.transform_anchor;rect=QRect(anchor,pt).normalized();width=max(1,rect.width());height=max(1,rect.height())
            if event.modifiers()&Qt.ShiftModifier:height=max(1,round(width*self.transform_source.image.height()/self.transform_source.image.width()))
            try:check_size(width,height)
            except ValueError:return
            l=doc.layer;source=self.transform_source
            if sum(layer.image.width()*layer.image.height()*4*(2 if layer.mask is not None else 1) for layer in doc.layers if layer is not l)+width*height*4*(2 if source.mask is not None else 1)>256*1024*1024:return
            l.image=source.image.scaled(width,height,Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
            if source.mask is not None:l.mask=source.mask.scaled(width,height,Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
            l.x=anchor.x()-width+1 if self.transform_corner in (0,2) else anchor.x();l.y=anchor.y()-height+1 if self.transform_corner in (0,1) else anchor.y();l.text=None
            doc.invalidate();w.modified();self.update();return
        if w.tool in ('Sélection','Recadrer'):self.selection=QRect(self.start,pt).normalized().intersected(QRect(0,0,doc.width,doc.height))
        elif w.tool=='Lasso':self.selection.lineTo(pt)
        elif w.tool in ('Pinceau','Gomme'):doc.stroke(self.last,pt,w.color,w.brush_size.value(),w.tool=='Gomme',self.selection,w.mask_edit);w.modified()
        elif w.tool in ('Déplacer','Transformer'):
            delta=pt-self.start;doc.layer.x=max(-16384,min(16384,self.origin.x()+delta.x()));doc.layer.y=max(-16384,min(16384,self.origin.y()+delta.y()));doc.invalidate();w.modified()
        self.last=pt;self.update()
    def mouseReleaseEvent(self,event):
        if self.pan_start is not None:
            self.pan_start=None;self.setCursor(Qt.OpenHandCursor if self.space else Qt.CrossCursor);return
        if not self.dragging or event.button()!=Qt.LeftButton:return
        self.dragging=False;w=self.window
        if self.transform_corner is not None:
            result=w.project.state();w.project.restore(self.transform_state);w.project.checkpoint();w.project.restore(result);self.transform_corner=None;w.modified();w.refresh();self.update();return
        if w.tool=='Lasso':self.selection.closeSubpath();self.update();return
        if w.tool in ('Rectangle','Ellipse'):
            rect=QRect(self.start,self.point(event)).normalized();l=w.project.layer;p=QPainter(l.mask if w.mask_edit and l.mask is not None else l.image);p.setRenderHint(QPainter.Antialiasing)
            if self.selection:w.clip(p,self.selection,l)
            p.setPen(QPen(w.color,w.brush_size.value()));p.setBrush(Qt.NoBrush);rect.translate(-l.x,-l.y)
            p.drawEllipse(rect) if w.tool=='Ellipse' else p.drawRect(rect);p.end();w.project.invalidate();w.modified()
        elif w.tool=='Recadrer' and self.selection and not self.selection.isEmpty():
            if QMessageBox.question(w,'Recadrer','Recadrer tous les calques à la zone choisie ?')==QMessageBox.Yes:
                w.project.crop(self.selection);self.selection=None;w.modified();self.sync()
        w.refresh();self.update()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Space and not event.isAutoRepeat():self.space=True;self.setCursor(Qt.OpenHandCursor);event.accept();return
        if event.key()==Qt.Key_Escape:
            if self.transform_corner is not None:
                self.window.project.restore(self.transform_state);self.transform_corner=None;self.dragging=False;self.window.refresh()
            else:self.window.deselect()
            event.accept();return
        super().keyPressEvent(event)
    def keyReleaseEvent(self,event):
        if event.key()==Qt.Key_Space and not event.isAutoRepeat():self.space=False;self.setCursor(Qt.CrossCursor);event.accept();return
        super().keyReleaseEvent(event)
    def focusOutEvent(self,event):
        self.space=False;self.pan_start=None;super().focusOutEvent(event)
    def mouseDoubleClickEvent(self,event):
        if self.window.project.layer.text is not None:self.window.edit_text()
        else:super().mouseDoubleClickEvent(event)
    def wheelEvent(self,event):
        if event.modifiers()&Qt.ControlModifier:
            self.window.set_zoom(self.zoom*(1.15 if event.angleDelta().y()>0 else 1/1.15));event.accept()
        else:event.ignore()


class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.resize(1360,880);self.project=Project();self.path=None;self.document_title='Sans titre';self.dirty=False;self.tool='Pinceau';self.color=QColor('#9273e8');self.syncing=False;self.mask_edit=False
        self.canvas=Canvas(self);self.scroll=QScrollArea();self.scroll.setWidget(self.canvas);self.scroll.setAlignment(Qt.AlignCenter);self.scroll.setWidgetResizable(False);self.tabs=QTabBar();self.tabs.setTabsClosable(True);self.tabs.setExpanding(False)
        central=QWidget();layout=QVBoxLayout(central);layout.setContentsMargins(0,0,0,0);layout.setSpacing(0);layout.addWidget(self.tabs);layout.addWidget(self.scroll,1);self.setCentralWidget(central)
        self.build_toolbar();self.build_tools();self.build_layers();self.build_menu();self.style();self.refresh();self.canvas.sync()
        self.sessions=[self.session_state()];self.session_index=0;self.tabs.addTab('Sans titre');self.tabs.currentChanged.connect(self.switch_session);self.tabs.tabCloseRequested.connect(self.close_session);self.set_tool('Pinceau')
        self.recovery=Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))/'recovery.atelier';self.recovery.parent.mkdir(parents=True,exist_ok=True)
        self.timer=QTimer(self);self.timer.timeout.connect(self.autosave);self.timer.start(30000);QTimer.singleShot(0,self.offer_recovery)
    def action(self,label,fn,key=None,check=False):
        a=QAction(label,self);a.setCheckable(check)
        if key:a.setShortcut(QKeySequence(key))
        a.triggered.connect(fn);return a
    def button(self,label,fn,primary=False):
        b=QPushButton(label);b.clicked.connect(fn)
        if primary:b.setProperty('primary',True)
        return b
    def build_toolbar(self):
        tb=QToolBar('Document');tb.setMovable(False);self.addToolBar(tb)
        box=QWidget();row=QHBoxLayout(box);row.setContentsMargins(16,8,16,8);row.setSpacing(10)
        brand=QLabel('atelier');brand.setObjectName('brand');row.addWidget(brand)
        subtitle=QLabel('Images · idées · créations');subtitle.setObjectName('muted');row.addWidget(subtitle);row.addStretch()
        for label,fn in [('Nouveau',self.new),('Ouvrir',self.open),('Importer un calque',self.import_layer),('Enregistrer',self.save),('Exporter',self.export)]:row.addWidget(self.button(label,fn,label=='Enregistrer'))
        box.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred);tb.addWidget(box)
        self.addToolBarBreak();options=QToolBar('Options');options.setMovable(False);self.addToolBar(options)
        self.color_button=self.button('Couleur',self.choose_color);options.addWidget(self.color_button)
        self.brush_caption=options.addWidget(QLabel('  Taille du pinceau  '));self.brush_size=QSpinBox();self.brush_size.setRange(1,400);self.brush_size.setValue(18);self.brush_action=options.addWidget(self.brush_size)
        options.addSeparator();self.font=QFontComboBox();self.font.setFixedWidth(175);self.font_action=options.addWidget(self.font)
        self.text_size=QSpinBox();self.text_size.setRange(6,400);self.text_size.setValue(48);self.size_action=options.addWidget(self.text_size);self.text_hint=QLabel(' px · texte modifiable  ');self.text_hint_action=options.addWidget(self.text_hint)
        options.addSeparator();options.addAction(self.action('Annuler',self.undo,'Ctrl+Z'));options.addAction(self.action('Rétablir',self.redo,'Ctrl+Shift+Z'))
        options.addSeparator();options.addAction(self.action('Ajuster à la fenêtre',self.fit));options.addAction(self.action('100 %',lambda:self.set_zoom(1)))
        options.addSeparator();self.tool_hint=QLabel(' Pinceau · dessinez sur le calque actif ');options.addWidget(self.tool_hint)
        self.options_bar=options;self.set_color(self.color)
    def build_tools(self):
        tb=QToolBar('Outils');tb.setMovable(False);tb.setOrientation(Qt.Vertical);self.addToolBar(Qt.LeftToolBarArea,tb)
        group=QActionGroup(self);group.setExclusive(True)
        for label,key,glyph in [('Déplacer','V','↔'),('Sélection','M','▧'),('Lasso','L',''),('Transformer','Ctrl+T',''),('Pinceau','B','✎'),('Gomme','E','▱'),('Texte','T','T'),('Rectangle','R','□'),('Ellipse','O','○'),('Pipette','I','◉'),('Remplir','G','▰'),('Recadrer','C','⌗')]:
            action=self.action(label,lambda checked=False,t=label:self.set_tool(t),key,True);action.setToolTip(f'{label} · {key}');group.addAction(action)
            name={'Déplacer':'move','Sélection':'select','Lasso':'lasso','Transformer':'transform','Pinceau':'brush','Gomme':'eraser','Texte':'text','Rectangle':'rectangle','Ellipse':'ellipse','Pipette':'pipette','Remplir':'fill','Recadrer':'crop'}[label]
            action.setIcon(vector_icon(name,'#d5c9ff'));b=QToolButton();b.setDefaultAction(action);b.setToolButtonStyle(Qt.ToolButtonIconOnly);b.setIconSize(QSize(24,24));b.setFixedSize(44,44);b.setStyleSheet('padding:8px;');tb.addWidget(b)
            if label=='Pinceau':action.setChecked(True)
        self.tool_group=group
    def build_layers(self):
        dock=QDockWidget('Calques',self);dock.setFeatures(QDockWidget.NoDockWidgetFeatures);dock.setMinimumWidth(255);dock.setMaximumWidth(300)
        box=QWidget();layout=QVBoxLayout(box);layout.setContentsMargins(16,18,16,16);layout.setSpacing(12)
        caption=QLabel('Votre composition');caption.setObjectName('panelTitle');layout.addWidget(caption)
        hint=QLabel('Le calque du haut apparaît au premier plan.');hint.setWordWrap(True);hint.setObjectName('muted');layout.addWidget(hint)
        self.layers=QListWidget();self.layers.setIconSize(QSize(38,32));self.layers.setMinimumHeight(170);self.layers.setTextElideMode(Qt.ElideRight);self.layers.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.layers.currentRowChanged.connect(self.layer_selected);self.layers.itemChanged.connect(self.visibility);self.layers.itemDoubleClicked.connect(self.edit_layer);layout.addWidget(self.layers,1)
        layout.addWidget(QLabel('OPACITÉ'));self.opacity=QSpinBox();self.opacity.setRange(0,100);self.opacity.setSuffix(' %');self.opacity.valueChanged.connect(self.change_opacity);layout.addWidget(self.opacity)
        layout.addWidget(QLabel('MODE DE FUSION'));self.blend=QComboBox();self.blend.addItems(list(MODES));self.blend.currentTextChanged.connect(self.change_blend);layout.addWidget(self.blend)
        self.locked=QCheckBox('Verrouiller le calque');self.locked.toggled.connect(self.lock_layer);layout.addWidget(self.locked)
        mask_row=QHBoxLayout();mask_row.addWidget(self.button('Ajouter un masque',self.add_mask));mask_row.addWidget(self.button('Retirer',self.remove_mask));layout.addLayout(mask_row)
        self.mask_toggle=QCheckBox('Modifier le masque');self.mask_toggle.toggled.connect(self.set_mask_edit);self.mask_toggle.setToolTip('Le pinceau peint le masque. Utilisez noir pour cacher et blanc pour révéler.');layout.addWidget(self.mask_toggle)
        self.mask_enabled=QCheckBox('Activer le masque');self.mask_enabled.toggled.connect(self.enable_mask);layout.addWidget(self.mask_enabled)
        self.mask_colors_box=QWidget();mask_colors=QHBoxLayout(self.mask_colors_box);mask_colors.setContentsMargins(0,0,0,0);mask_colors.addWidget(self.button('Noir',lambda:self.set_color(QColor('black'))));mask_colors.addWidget(self.button('Blanc',lambda:self.set_color(QColor('white'))));layout.addWidget(self.mask_colors_box)
        layout.addWidget(self.button('Ajouter un calque',lambda:self.add_layer(),True))
        row=QHBoxLayout()
        for label,fn in [('Monter',lambda:self.reorder(1)),('Descendre',lambda:self.reorder(-1))]:row.addWidget(self.button(label,fn))
        layout.addLayout(row)
        row=QHBoxLayout()
        for label,fn in [('Dupliquer',self.duplicate),('Renommer',self.rename)]:row.addWidget(self.button(label,fn))
        layout.addLayout(row);layout.addWidget(self.button('Supprimer',self.delete_layer))
        note=QLabel('PNG conserve la transparence.\n.atelier conserve vos calques.');note.setObjectName('muted');layout.addWidget(note)
        dock.setWidget(box);self.addDockWidget(Qt.RightDockWidgetArea,dock);self.layers_dock=dock
        self.build_properties()
    def build_menu(self):
        f=self.menuBar().addMenu('Fichier')
        for label,fn,key in [('Nouveau',self.new,'Ctrl+N'),('Ouvrir…',self.open,'Ctrl+O'),('Enregistrer',self.save,'Ctrl+S'),('Enregistrer sous…',lambda:self.save(True),'Ctrl+Shift+S'),('Importer un calque…',self.import_layer,None),('Exporter PNG / JPEG…',self.export,'Ctrl+Shift+E')]:f.addAction(self.action(label,fn,key))
        e=self.menuBar().addMenu('Édition');e.addAction(self.action('Annuler',self.undo));e.addAction(self.action('Rétablir',self.redo));e.addAction(self.action('Effacer la zone sélectionnée',self.clear_selection,'Delete'));e.addAction(self.action('Désélectionner',self.deselect,'Ctrl+D'));e.addAction(self.action('Copier la sélection sur un calque',self.selection_to_layer,'Ctrl+J'));e.addAction(self.action('Modifier le texte',self.edit_text));e.addAction(self.action('Rasteriser le texte',self.rasterize))
        image=self.menuBar().addMenu('Image');image.addAction(self.action('Redimensionner…',self.resize_image));image.addAction(self.action('Transformer le calque…',self.transform_dialog));image.addAction(self.action('Rotation du calque à 90°',self.rotate));image.addAction(self.action('Miroir horizontal du calque',self.mirror))
        adjust=self.menuBar().addMenu('Réglages')
        for name in ['Luminosité','Contraste','Saturation','Netteté','Flou','Noir et blanc','Inverser les couleurs']:adjust.addAction(self.action(name,lambda checked=False,k=name:self.adjust(k)))
        view=self.menuBar().addMenu('Affichage');view.addAction(self.action('Ajuster à la fenêtre',self.fit));view.addAction(self.action('Zoom +',lambda:self.set_zoom(self.canvas.zoom*1.2),'Ctrl++'));view.addAction(self.action('Zoom −',lambda:self.set_zoom(self.canvas.zoom/1.2),'Ctrl+-'))
        help=self.menuBar().addMenu('Aide');help.addAction(self.action('À propos',lambda:QMessageBox.information(self,APP,'Atelier 0.2\n\nCalques, masques, lasso, transformations et texte modifiable.\nEspace + glisser : déplacer la vue. Ctrl+molette : zoom.\nCtrl+T : poignées de transformation. Maj : proportions.\nPSD, RAW et outils de retouche avancée restent à développer.')))
    def style(self):
        palette=QPalette()
        for role,value in [(QPalette.Window,'#222631'),(QPalette.WindowText,'#e8eaf1'),(QPalette.Base,'#292f3d'),(QPalette.Text,'#e8eaf1'),(QPalette.Button,'#2a303e'),(QPalette.ButtonText,'#e8eaf1'),(QPalette.Highlight,'#7560b8'),(QPalette.HighlightedText,'#ffffff')]:palette.setColor(role,QColor(value))
        QApplication.instance().setPalette(palette)
        self.setStyleSheet('''QWidget{font-family:"Segoe UI","DejaVu Sans";font-size:12px;color:#e8eaf1;background:#222631}
        QMainWindow,QScrollArea,QScrollArea>QWidget>QWidget{background:#161922;border:0}
        QMenuBar{padding:5px 12px;border-bottom:1px solid #353b4b} QMenuBar::item{padding:5px 12px}QMenuBar::item:selected,QMenu::item:selected{background:#45405c}
        QMenu{padding:6px;border:1px solid #454b60}QMenu::item{padding:8px 24px}
        QToolBar{spacing:7px;padding:8px;border:0;border-bottom:1px solid #353b4b}
        QLabel#brand{font-size:26px;font-weight:700;color:#beabfb}QLabel#muted{color:#acb3c6;font-size:11px}QLabel#panelTitle{font-size:17px;font-weight:600}
        QPushButton,QToolButton{padding:7px 10px;border:1px solid #3b4254;border-radius:7px;background:#2a303e;color:#e8eaf1;min-height:18px}
        QPushButton:hover,QToolButton:hover{background:#373d50}QToolButton:checked,QPushButton[primary="true"]{background:#7560b8;border-color:#8c75d1;color:white}
        QLineEdit,QTextEdit,QComboBox,QSpinBox{padding:5px;background:#292f3d;border:1px solid #444b60;border-radius:5px;selection-background-color:#7560b8;selection-color:white}
        QComboBox QAbstractItemView{background:#292f3d;color:#e8eaf1;selection-background-color:#7560b8;selection-color:white;border:1px solid #555e76}
        QListWidget{background:#1d212c;border:1px solid #363d4e;border-radius:8px;outline:0}QListWidget::item{padding:12px 8px;margin:3px;border-radius:6px}QListWidget::item:selected{background:#45405f}
        QDockWidget::title{padding:10px 16px;font-weight:600}QStatusBar{padding:5px 12px;background:#222631;color:#b7bfd2;border-top:1px solid #353b4b}
        QScrollBar:vertical{width:12px;background:#20242f}QScrollBar::handle:vertical{background:#495166;min-height:28px;border-radius:5px}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}
        QTabBar::tab{background:#222631;padding:10px 16px;border-right:1px solid #373d4e}QTabBar::tab:selected{background:#343a4a;color:#ddd1ff}QCheckBox{spacing:6px;font-size:11px}QToolTip{background:#353b4b;color:white;border:1px solid #656d84;padding:6px}''')
    def set_tool(self,tool):
        self.tool=tool;self.canvas.setCursor(Qt.CrossCursor if tool!='Déplacer' else Qt.SizeAllCursor)
        self.font_action.setVisible(tool=='Texte');self.size_action.setVisible(tool=='Texte');self.text_hint_action.setVisible(tool=='Texte');self.brush_action.setVisible(tool in ('Pinceau','Gomme','Rectangle','Ellipse'));self.brush_caption.setVisible(tool in ('Pinceau','Gomme','Rectangle','Ellipse'))
        hints={'Transformer':'Glissez une poignée · Maj : proportions · Échap : annuler','Déplacer':'Glissez le calque actif · Espace : déplacer la vue','Lasso':'Tracez une sélection à main levée','Texte':'Cliquez pour ajouter · double-clic pour modifier','Recadrer':'Tracez puis confirmez le recadrage','Sélection':'Tracez une sélection rectangulaire','Remplir':'Remplit la sélection ou le calque dans le document'}
        self.tool_hint.setText(' '+hints.get(tool,'Dessinez sur le calque actif ou son masque')+' ');self.canvas.update();self.status()
    def set_color(self,color):self.color=QColor(color);self.color_button.setStyleSheet(f'background:{self.color.name()};color:{"#ffffff" if self.color.lightness()<160 else "#202020"};');self.color_button.setText(self.color.name().upper())
    def choose_color(self):
        from PySide6.QtWidgets import QColorDialog
        color=QColorDialog.getColor(self.color,self,'Couleur')
        if color.isValid():self.set_color(color)
    def status(self):
        p=self.project;self.setWindowTitle(f'{"● " if self.dirty else ""}{self.path.name if self.path else self.document_title} — Atelier')
        if hasattr(self,'sessions'):
            self.tabs.setTabText(self.session_index,('● ' if self.dirty else '')+(self.path.name if self.path else self.document_title))
        self.statusBar().showMessage(f'{p.width} × {p.height} px   ·   {round(self.canvas.zoom*100)} %   ·   {self.tool}   ·   {len(p.layers)} calque(s)   ·   '+('Modifications non enregistrées' if self.dirty else 'Prêt'))
    def modified(self):self.dirty=True;self.project.invalidate();self.canvas.update();self.status()
    def refresh(self):
        self.syncing=True;self.layers.clear()
        for l in reversed(self.project.layers):
            item=QListWidgetItem(('▣ ' if l.mask is not None else '')+('T · ' if l.text is not None else '')+('Verrouillé · ' if l.locked else '')+l.name);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked if l.visible else Qt.Unchecked)
            pix=QPixmap.fromImage(l.effective().scaled(38,30,Qt.KeepAspectRatio,Qt.SmoothTransformation));item.setIcon(QIcon(pix));self.layers.addItem(item)
        self.layers.setCurrentRow(len(self.project.layers)-1-self.project.active);self.opacity.setValue(self.project.layer.opacity);self.blend.setCurrentText(self.project.layer.mode);self.locked.setChecked(self.project.layer.locked)
        has_mask=self.project.layer.mask is not None;self.mask_colors_box.setVisible(has_mask);self.mask_toggle.setVisible(has_mask);self.mask_enabled.setVisible(has_mask);self.mask_toggle.setEnabled(has_mask);self.mask_enabled.setEnabled(has_mask);self.mask_edit=self.mask_edit and has_mask;self.mask_toggle.setChecked(self.mask_edit);self.mask_enabled.setChecked(has_mask and self.project.layer.mask_enabled)
        self.syncing=False;self.status();self.canvas.update()
        if hasattr(self,'history'):self.refresh_properties()
    def layer_selected(self,row):
        if self.syncing or row<0:return
        self.project.active=len(self.project.layers)-1-row;self.mask_edit=False;self.refresh()
    def visibility(self,item):
        if self.syncing:return
        self.project.checkpoint();self.project.layers[len(self.project.layers)-1-self.layers.row(item)].visible=item.checkState()==Qt.Checked;self.modified()
    def change_opacity(self,value):
        if self.syncing:return
        self.project.checkpoint();self.project.layer.opacity=value;self.modified()
    def change_blend(self,value):
        if self.syncing:return
        self.project.checkpoint();self.project.layer.mode=value;self.modified()
    def add_layer(self):
        result=self.io(lambda:self.project.add(f'Calque {len(self.project.layers)+1}'))
        if result:self.modified();self.refresh()
    def duplicate(self):
        if len(self.project.layers)>=100 or sum(l.image.width()*l.image.height()*4*(2 if l.mask is not None else 1) for l in self.project.layers)+self.project.layer.image.width()*self.project.layer.image.height()*4*(2 if self.project.layer.mask is not None else 1)>256*1024*1024:
            QMessageBox.information(self,'Calques','Limite de 100 calques ou 256 Mo de pixels atteinte.');return
        self.project.checkpoint();l=self.project.layer.copy();l.name+=' — copie';self.project.layers.insert(self.project.active+1,l);self.project.active+=1;self.modified();self.refresh()
    def reorder(self,delta):
        p=self.project;i=p.active;j=i+delta
        if 0<=j<len(p.layers):p.checkpoint();p.layers[i],p.layers[j]=p.layers[j],p.layers[i];p.active=j;self.modified();self.refresh()
    def rename(self,*args):
        name,ok=QInputDialog.getText(self,'Renommer','Nom du calque',text=self.project.layer.name)
        if ok and name.strip():self.project.checkpoint();self.project.layer.name=name.strip();self.modified();self.refresh()
    def delete_layer(self):
        if len(self.project.layers)==1:QMessageBox.information(self,'Calque','Gardez au moins un calque. Utilisez Effacer pour le vider.');return
        if QMessageBox.question(self,'Supprimer','Supprimer le calque actif ?')==QMessageBox.Yes:self.project.checkpoint();self.project.layers.pop(self.project.active);self.project.active=min(self.project.active,len(self.project.layers)-1);self.modified();self.refresh()
    def undo(self):
        if self.project.undo():self.canvas.selection=None;self.modified();self.refresh();self.canvas.sync()
    def redo(self):
        if self.project.redo():self.canvas.selection=None;self.modified();self.refresh();self.canvas.sync()
    def deselect(self):self.canvas.selection=None;self.canvas.update()
    def ensure_pixels(self):
        if self.project.layer.locked:return False
        if not self.mask_edit and self.project.layer.text is not None:
            if QMessageBox.question(self,'Rasteriser le texte','Cet outil transforme le texte en pixels. Continuer ?')!=QMessageBox.Yes:return False
            self.project.checkpoint();self.project.layer.text=None;self.modified();self.refresh()
        return True
    @staticmethod
    def clip(painter,selection,layer):
        if isinstance(selection,QPainterPath):painter.setClipPath(QTransform().translate(-layer.x,-layer.y).map(selection))
        else:painter.setClipRect(selection.translated(-layer.x,-layer.y))
    def fill(self):
        if not self.ensure_pixels():return
        self.project.checkpoint();l=self.project.layer;p=QPainter(l.mask if self.mask_edit and l.mask is not None else l.image)
        if self.canvas.selection:self.clip(p,self.canvas.selection,l)
        color=self.color
        if self.mask_edit:v=color.lightness();color=QColor(v,v,v)
        p.fillRect(QRect(0,0,self.project.width,self.project.height).translated(-l.x,-l.y),color);p.end();self.modified();self.refresh()
    def clear_selection(self):
        if not self.ensure_pixels():return
        self.project.checkpoint();l=self.project.layer;p=QPainter(l.mask if self.mask_edit and l.mask is not None else l.image)
        if self.canvas.selection:self.clip(p,self.canvas.selection,l)
        if not self.mask_edit:p.setCompositionMode(QPainter.CompositionMode_Clear)
        p.fillRect(QRect(0,0,self.project.width,self.project.height).translated(-l.x,-l.y),Qt.black if self.mask_edit else Qt.transparent);p.end();self.modified();self.refresh()
    def text_dialog(self,spec=None):
        from PySide6.QtWidgets import QTextEdit
        dialog=QDialog(self);dialog.setWindowTitle('Texte modifiable');layout=QVBoxLayout(dialog)
        content=QTextEdit();content.setPlainText(spec['content'] if spec else '');layout.addWidget(content)
        family=QFontComboBox();family.setCurrentFont(QFont(spec['family']) if spec else self.font.currentFont());layout.addWidget(family)
        size=QSpinBox();size.setRange(6,400);size.setValue(spec['size'] if spec else self.text_size.value());size.setSuffix(' px');layout.addWidget(size)
        color=QColor(spec['color']) if spec else QColor(self.color)
        button=QPushButton('Couleur du texte');layout.addWidget(button)
        def choose():
            nonlocal color
            chosen=QColorDialog.getColor(color,dialog)
            if chosen.isValid():color=chosen
        button.clicked.connect(choose)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()!=QDialog.Accepted or not content.toPlainText():return None
        return {'content':content.toPlainText()[:10000],'family':family.currentFont().family(),'size':size.value(),'color':color.name()}
    def add_text(self,pt):
        spec=self.text_dialog()
        if spec and self.io(lambda:self.project.set_text(spec,True,pt.x(),pt.y())):self.modified();self.refresh()
    def edit_layer(self,*args):self.edit_text() if self.project.layer.text is not None else self.rename()
    def edit_text(self):
        if self.project.layer.text is None or self.project.layer.locked:return
        spec=self.text_dialog(self.project.layer.text)
        if spec and self.io(lambda:self.project.set_text(spec)):self.modified();self.refresh()
    def rasterize(self):
        if self.project.layer.text is not None and not self.project.layer.locked:self.project.checkpoint();self.project.layer.text=None;self.modified();self.refresh()
    def rotate(self):
        l=self.project.layer
        if self.io(lambda:self.project.transform_layer(l.image.width(),l.image.height(),90)):
            self.modified();self.refresh()
    def mirror(self):
        if self.project.layer.locked:return
        self.project.checkpoint();l=self.project.layer;l.image=l.image.mirrored(True,False)
        if l.mask is not None:l.mask=l.mask.mirrored(True,False)
        l.text=None;self.modified();self.refresh()
    def resize_image(self):
        w,ok=QInputDialog.getInt(self,'Redimensionner','Largeur en pixels',self.project.width,1,8192)
        if not ok:return
        h,ok=QInputDialog.getInt(self,'Redimensionner','Hauteur en pixels',round(w*self.project.height/self.project.width),1,8192)
        if ok:self.io(lambda:self.project.resize(w,h));self.modified();self.canvas.selection=None;self.canvas.sync();self.refresh()
    def adjust(self,kind):
        if not self.ensure_pixels():return
        value=1
        if kind not in ('Noir et blanc','Inverser les couleurs'):
            value,ok=QInputDialog.getDouble(self,kind,'Valeur (1 = inchangé)' if kind!='Flou' else 'Rayon du flou en pixels',1,0,20 if kind=='Flou' else 5,2)
            if not ok:return
        self.io(lambda:self.project.adjust(kind,value));self.modified();self.refresh()
    def set_zoom(self,value):self.canvas.zoom=max(.05,min(8,value));self.canvas.sync();self.status()
    def fit(self):
        size=self.scroll.viewport().size();self.set_zoom(min((size.width()-64)/self.project.width,(size.height()-64)/self.project.height,2))
    def io(self,fn):
        try:return fn()
        except Exception as exc:QMessageBox.warning(self,'Opération impossible',str(exc));return None
    def confirm(self):
        if not self.dirty:return True
        answer=QMessageBox.question(self,'Enregistrer ?','Enregistrer votre projet avant de continuer ?',QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel)
        return self.save() if answer==QMessageBox.Save else answer==QMessageBox.Discard
    def replace_project(self,p,path=None):
        self.open_session(p,path)
    def new(self):
        w,ok=QInputDialog.getInt(self,'Nouveau document','Largeur en pixels',1000,1,8192)
        if not ok:return
        h,ok=QInputDialog.getInt(self,'Nouveau document','Hauteur en pixels',700,1,8192)
        if ok:
            p=self.io(lambda:Project(w,h))
            if p:self.replace_project(p)
    def open(self):
        path,_=QFileDialog.getOpenFileName(self,'Ouvrir','','Images et projets (*.atelier *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)')
        if not path:return
        def perform():
            if Path(path).suffix.lower()=='.atelier':self.replace_project(Project.load(path),Path(path))
            else:
                image=load_image(path);p=Project(image.width(),image.height());p.layers=[Layer(Path(path).stem,image)];self.open_session(p,title=Path(path).name)
        self.io(perform)
    def import_layer(self):
        path,_=QFileDialog.getOpenFileName(self,'Importer un calque','','Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)')
        if path:
            def perform():
                image=load_image(path)
                if image.width()>self.project.width or image.height()>self.project.height:image=image.scaled(self.project.width,self.project.height,Qt.KeepAspectRatio,Qt.SmoothTransformation)
                self.project.add(Path(path).stem,image);self.modified();self.refresh()
            self.io(perform)
    def save(self,save_as=False):
        path=self.path
        if save_as or not path:
            name,_=QFileDialog.getSaveFileName(self,'Enregistrer le projet',str(path or 'Ma création.atelier'),'Projet Atelier (*.atelier)')
            if not name:return False
            path=Path(name if name.lower().endswith('.atelier') else name+'.atelier')
        try:
            self.project.save(path);self.path=path;self.dirty=False;self.recovery.unlink(missing_ok=True);self.store_session()
            if any(state['dirty'] for state in self.sessions):self.autosave()
            else:self.recovery.with_suffix('.workspace').unlink(missing_ok=True)
            self.status();return True
        except Exception as exc:QMessageBox.warning(self,'Enregistrement impossible',str(exc));return False
    def export(self):
        name,selected=QFileDialog.getSaveFileName(self,'Exporter','Ma création.png','PNG transparent (*.png);;JPEG fond blanc (*.jpg)')
        if not name:return
        jpeg=selected.startswith('JPEG');suffix='.jpg' if jpeg else '.png';path=Path(name)
        if path.suffix.lower() not in (('.jpg','.jpeg') if jpeg else ('.png',)):path=Path(name+suffix)
        def perform():
            import os,tempfile
            image=self.project.composite()
            if jpeg:
                bg=QImage(image.size(),QImage.Format_RGB32);bg.fill(Qt.white);p=QPainter(bg);p.drawImage(0,0,image);p.end();image=bg
            fd,tmp=tempfile.mkstemp(dir=path.parent,suffix=suffix);os.close(fd)
            try:
                if not image.save(tmp,'JPEG' if jpeg else 'PNG',95):raise OSError('Export impossible.')
                os.replace(tmp,path)
            finally:Path(tmp).unlink(missing_ok=True)
            self.statusBar().showMessage('Image exportée · Enregistrez aussi en .atelier pour conserver vos calques.',6000)
        self.io(perform)
    def session_state(self):return {'project':self.project,'path':self.path,'dirty':self.dirty,'zoom':self.canvas.zoom,'selection':self.canvas.selection,'mask_edit':self.mask_edit,'title':self.document_title}
    def store_session(self):
        if hasattr(self,'sessions'):self.sessions[self.session_index]=self.session_state()
    def open_session(self,p,path=None,title=None):
        if len(self.sessions)>=20:QMessageBox.information(self,'Documents','Fermez un onglet avant d’en ouvrir un autre (20 maximum).');return
        self.store_session();state={'project':p,'path':path,'dirty':path is None,'zoom':1,'selection':None,'mask_edit':False,'title':title or (path.name if path else f'Sans titre {len(self.sessions)+1}')}
        if len(self.sessions)==1 and not self.dirty and self.path is None and len(self.project.layers)==1 and not self.project.undo_stack:
            self.sessions[0]=state;self.load_session(0)
        else:
            self.sessions.append(state);self.tabs.blockSignals(True);self.tabs.addTab(path.name if path else 'Sans titre');self.tabs.setCurrentIndex(len(self.sessions)-1);self.tabs.blockSignals(False);self.load_session(len(self.sessions)-1)
        self.fit()
    def load_session(self,index):
        self.session_index=index;s=self.sessions[index];self.document_title=s.get('title','Sans titre');self.project=s['project'];self.path=s['path'];self.dirty=s['dirty'];self.canvas.zoom=s['zoom'];self.canvas.selection=s['selection'];self.mask_edit=s['mask_edit'];self.refresh();self.canvas.sync()
    def switch_session(self,index):
        if index<0 or index==self.session_index:return
        if self.canvas.dragging:
            self.tabs.blockSignals(True);self.tabs.setCurrentIndex(self.session_index);self.tabs.blockSignals(False);return
        self.store_session();self.load_session(index)
    def close_session(self,index):
        self.tabs.setCurrentIndex(index)
        if not self.confirm():return
        self.store_session()
        if len(self.sessions)==1:
            self.sessions[0]={'project':Project(),'path':None,'dirty':False,'zoom':1,'selection':None,'mask_edit':False};self.load_session(0);return
        self.tabs.blockSignals(True);self.sessions.pop(index);self.tabs.removeTab(index);target=min(index,len(self.sessions)-1);self.tabs.setCurrentIndex(target);self.tabs.blockSignals(False);self.load_session(target)
    def build_properties(self):
        dock=QDockWidget('Propriétés & historique',self);dock.setMinimumWidth(255);dock.setMaximumWidth(300);box=QWidget();layout=QVBoxLayout(box)
        self.properties=QLabel();self.properties.setWordWrap(True);layout.addWidget(self.properties)
        layout.addWidget(self.button('Transformer / rotation…',self.transform_dialog));layout.addWidget(self.button('Modifier le texte',self.edit_text));layout.addWidget(self.button('Copier sélection sur un calque',self.selection_to_layer))
        layout.addWidget(QLabel('HISTORIQUE'));self.history=QListWidget();self.history.itemClicked.connect(self.history_undo);layout.addWidget(self.history,1)
        hint=QLabel('Espace + glisser : déplacer la vue\nCtrl + molette : zoom\nCtrl+T : transformer · Ctrl+J : copie');hint.setObjectName('muted');layout.addWidget(hint)
        dock.setWidget(box);self.addDockWidget(Qt.RightDockWidgetArea,dock);self.tabifyDockWidget(self.layers_dock,dock);self.layers_dock.raise_()
    def refresh_properties(self):
        l=self.project.layer;self.properties.setText(f'{l.name}\n{l.image.width()} × {l.image.height()} px\nPosition : {l.x}, {l.y}\n'+('Texte modifiable' if l.text else 'Pixels')+(' · masque' if l.mask is not None else ''))
        self.history.clear();self.history.addItem('État le plus ancien conservé')
        for index in range(len(self.project.undo_stack)):self.history.addItem(f'{index+1:02} · {self.project.undo_titles[index]}')
        self.history.setCurrentRow(self.history.count()-1)
    def history_undo(self,item):
        target=self.history.row(item);count=len(self.project.undo_stack)-target
        for _ in range(max(0,count)):self.project.undo()
        if count>0:self.modified();self.canvas.selection=None;self.refresh();self.canvas.sync()
    def lock_layer(self,checked):
        if self.syncing:return
        self.project.checkpoint();self.project.layer.locked=checked;self.modified();self.refresh()
    def add_mask(self):
        if self.project.layer.locked:return
        if self.io(lambda:self.project.add_mask(self.canvas.selection)):self.mask_edit=True;self.modified();self.refresh();self.set_color(QColor('black'))
    def remove_mask(self):
        if self.project.layer.mask is None or self.project.layer.locked:return
        if QMessageBox.question(self,'Retirer le masque','Retirer le masque et révéler les pixels cachés ?')==QMessageBox.Yes:self.project.checkpoint();self.project.layer.mask=None;self.mask_edit=False;self.modified();self.refresh()
    def set_mask_edit(self,checked):
        if not self.syncing:self.mask_edit=checked and self.project.layer.mask is not None;self.status()
    def enable_mask(self,checked):
        if self.syncing or self.project.layer.mask is None:return
        self.project.checkpoint();self.project.layer.mask_enabled=checked;self.modified();self.refresh()
    def selection_to_layer(self):
        if self.canvas.selection is None:QMessageBox.information(self,'Sélection','Tracez une sélection avant de la copier.');return
        source=self.project.layer;rect=self.canvas.selection.boundingRect().toAlignedRect() if isinstance(self.canvas.selection,QPainterPath) else self.canvas.selection
        rect=rect.intersected(QRect(0,0,self.project.width,self.project.height))
        if rect.isEmpty():return
        image=blank(rect.width(),rect.height());p=QPainter(image);p.translate(-rect.x(),-rect.y())
        if isinstance(self.canvas.selection,QPainterPath):p.setClipPath(self.canvas.selection)
        else:p.setClipRect(self.canvas.selection)
        p.drawImage(source.x,source.y,source.effective());p.end()
        if self.io(lambda:self.project.add(source.name+' — sélection',image)):
            self.project.layer.x=rect.x();self.project.layer.y=rect.y();self.modified();self.refresh()
    def transform_dialog(self):
        if self.project.layer.locked:return
        dialog=QDialog(self);dialog.setWindowTitle('Transformer le calque');layout=QVBoxLayout(dialog);form=QFormLayout();l=self.project.layer
        width=QSpinBox();width.setRange(1,8192);width.setValue(l.image.width());height=QSpinBox();height.setRange(1,8192);height.setValue(l.image.height());angle=QSpinBox();angle.setRange(-180,180)
        x=QSpinBox();x.setRange(-16384,16384);x.setValue(l.x);y=QSpinBox();y.setRange(-16384,16384);y.setValue(l.y)
        for label,control in [('Largeur (px)',width),('Hauteur (px)',height),('Angle (°)',angle),('Position X',x),('Position Y',y)]:form.addRow(label,control)
        layout.addLayout(form);preview=QLabel();preview.setFixedSize(320,220);preview.setAlignment(Qt.AlignCenter);layout.addWidget(preview)
        def update():
            try:
                check_size(width.value(),height.value());scale=min(280/width.value(),180/height.value());img=l.effective().scaled(max(1,round(width.value()*scale)),max(1,round(height.value()*scale)),Qt.IgnoreAspectRatio,Qt.SmoothTransformation).transformed(QTransform().rotate(angle.value()),Qt.SmoothTransformation);preview.setPixmap(QPixmap.fromImage(img).scaled(300,200,Qt.KeepAspectRatio,Qt.SmoothTransformation))
            except ValueError:preview.setText('Dimensions trop grandes')
        for control in (width,height,angle):control.valueChanged.connect(update)
        update();layout.addWidget(QLabel('Le texte devient des pixels après transformation.'))
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()==QDialog.Accepted:
            def perform():self.project.transform_layer(width.value(),height.value(),angle.value());self.project.layer.x=x.value();self.project.layer.y=y.value();return True
            if self.io(perform):self.modified();self.refresh()
    def autosave(self):
        self.store_session()
        if not any(s['dirty'] for s in self.sessions):return
        try:
            import json,zipfile,tempfile,os
            self.project.save(self.recovery)
            destination=self.recovery.with_suffix('.workspace')
            with tempfile.TemporaryDirectory(dir=self.recovery.parent) as tmp:
                archive=Path(tmp)/'recovery.zip';entries=[]
                with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
                    for i,state in enumerate(self.sessions):
                        name=f'documents/{i}.atelier';path=Path(tmp)/f'{i}.atelier';state['project'].save(path);z.write(path,name)
                        entries.append({'file':name,'name':state['path'].name if state['path'] else 'Sans titre'})
                    z.writestr('workspace.json',json.dumps({'active':self.session_index,'documents':entries}))
                os.replace(archive,destination)
        except Exception as exc:self.statusBar().showMessage('Copie de secours impossible : '+str(exc))
    def offer_recovery(self):
        workspace=self.recovery.with_suffix('.workspace')
        if not self.recovery.exists() and not workspace.exists():return
        if QMessageBox.question(self,'Reprendre votre travail','Restaurer les documents de la copie de secours ?')!=QMessageBox.Yes:
            self.recovery.unlink(missing_ok=True);workspace.unlink(missing_ok=True);return
        def recover():
            if workspace.exists():
                import json,zipfile,tempfile
                restored=[]
                with zipfile.ZipFile(workspace) as z,tempfile.TemporaryDirectory() as tmp:
                    manifest=json.loads(z.read('workspace.json'))
                    if not 1<=len(manifest['documents'])<=20:raise ValueError('Nombre de documents invalide.')
                    for i,entry in enumerate(manifest['documents']):
                        info=z.getinfo(entry['file'])
                        if info.file_size>300*1024*1024:raise ValueError('Document de secours trop volumineux.')
                        path=Path(tmp)/f'{i}.atelier';path.write_bytes(z.read(info));restored.append(Project.load(path))
                for i,project in enumerate(restored):self.open_session(project,title=manifest['documents'][i].get('name','Projet restauré'))
                self.tabs.setCurrentIndex(min(manifest['active'],len(self.sessions)-1));return
            self.open_session(Project.load(self.recovery))
        self.io(recover)
    def closeEvent(self,event):
        for index in range(len(self.sessions)):
            self.tabs.setCurrentIndex(index)
            if not self.confirm():event.ignore();return
        self.recovery.unlink(missing_ok=True);self.recovery.with_suffix('.workspace').unlink(missing_ok=True);event.accept()


def main():
    app=QApplication(sys.argv);app.setApplicationName(APP);app.setOrganizationName(APP);app.setStyle('Fusion')
    icon=Path(__file__).resolve().parent/'assets'/'app.ico'
    if icon.exists():app.setWindowIcon(QIcon(str(icon)))
    if sys.platform=='win32':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Atelier.ImageEditor.0.2')
    if '--smoke-test' in sys.argv:
        QStandardPaths.setTestModeEnabled(True);app.setApplicationName('Atelier-smoke');w=Window();w.show();QTimer.singleShot(200,app.quit);return app.exec()
    from PySide6.QtNetwork import QLocalServer,QLocalSocket
    socket=QLocalSocket();socket.connectToServer('Atelier-local-editor')
    if socket.waitForConnected(200):QMessageBox.information(None,APP,'Atelier est déjà ouvert.');return 0
    QLocalServer.removeServer('Atelier-local-editor');server=QLocalServer();server.listen('Atelier-local-editor')
    w=Window();w.show();QTimer.singleShot(0,w.fit);return app.exec()

if __name__=='__main__':sys.exit(main())
