import sys
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QSize, QSettings, QStandardPaths
from PySide6.QtGui import (QAction, QActionGroup, QKeySequence, QPainter, QColor, QPen,
    QFont, QImage, QTransform, QPixmap, QIcon, QPalette)
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QScrollArea,QToolBar,
    QDockWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QToolButton,QListWidget,
    QListWidgetItem,QSpinBox,QComboBox,QFontComboBox,QFileDialog,QMessageBox,
    QInputDialog,QSizePolicy)
from model import Project,Layer,blank,load_image,MODES

from icons import vector_icon

APP='Atelier'


class Canvas(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.zoom=1;self.selection=None;self.start=None;self.last=None;self.dragging=False
        self.setMouseTracking(True);self.setFocusPolicy(Qt.StrongFocus)
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
        if self.selection:p.drawRect(self.selection)
        if self.dragging and self.window.tool in ('Rectangle','Ellipse'):
            r=QRect(self.start,self.last).normalized();p.setPen(QPen(self.window.color,2/self.zoom));p.drawEllipse(r) if self.window.tool=='Ellipse' else p.drawRect(r)
        p.end()
    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton:return
        pt=self.point(event);w=self.window;doc=w.project
        if not QRect(0,0,doc.width,doc.height).contains(pt):return
        if w.tool=='Pipette':w.set_color(doc.composite().pixelColor(pt));return
        if w.tool=='Texte':w.add_text(pt);return
        if w.tool=='Remplir':w.fill();return
        self.dragging=True;self.start=self.last=pt
        if w.tool in ('Sélection','Recadrer'):
            self.selection=QRect(pt,pt)
        else:
            doc.checkpoint()
            if w.tool in ('Pinceau','Gomme'):doc.stroke(pt,pt,w.color,w.brush_size.value(),w.tool=='Gomme',self.selection)
            if w.tool=='Déplacer':self.origin=QPoint(doc.layer.x,doc.layer.y)
            w.modified()
        self.update()
    def mouseMoveEvent(self,event):
        if not self.dragging:return
        pt=self.point(event);w=self.window;doc=w.project
        if w.tool in ('Sélection','Recadrer'):self.selection=QRect(self.start,pt).normalized().intersected(QRect(0,0,doc.width,doc.height))
        elif w.tool in ('Pinceau','Gomme'):doc.stroke(self.last,pt,w.color,w.brush_size.value(),w.tool=='Gomme',self.selection);w.modified()
        elif w.tool=='Déplacer':
            delta=pt-self.start;doc.layer.x=max(-16384,min(16384,self.origin.x()+delta.x()));doc.layer.y=max(-16384,min(16384,self.origin.y()+delta.y()));doc.invalidate();w.modified()
        self.last=pt;self.update()
    def mouseReleaseEvent(self,event):
        if not self.dragging or event.button()!=Qt.LeftButton:return
        self.dragging=False;w=self.window
        if w.tool in ('Rectangle','Ellipse'):
            rect=QRect(self.start,self.point(event)).normalized();l=w.project.layer;p=QPainter(l.image);p.setRenderHint(QPainter.Antialiasing)
            if self.selection:p.setClipRect(self.selection.translated(-l.x,-l.y))
            p.setPen(QPen(w.color,w.brush_size.value()));p.setBrush(Qt.NoBrush);rect.translate(-l.x,-l.y)
            p.drawEllipse(rect) if w.tool=='Ellipse' else p.drawRect(rect);p.end();w.project.invalidate();w.modified()
        elif w.tool=='Recadrer' and self.selection and not self.selection.isEmpty():
            if QMessageBox.question(w,'Recadrer','Recadrer tous les calques à la zone choisie ?')==QMessageBox.Yes:
                w.project.crop(self.selection);self.selection=None;w.modified();self.sync()
        w.refresh();self.update()
    def wheelEvent(self,event):
        if event.modifiers()&Qt.ControlModifier:
            self.window.set_zoom(self.zoom*(1.15 if event.angleDelta().y()>0 else 1/1.15));event.accept()
        else:event.ignore()


class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.resize(1360,880);self.project=Project();self.path=None;self.dirty=False;self.tool='Pinceau';self.color=QColor('#9273e8');self.syncing=False
        self.canvas=Canvas(self);self.scroll=QScrollArea();self.scroll.setWidget(self.canvas);self.scroll.setAlignment(Qt.AlignCenter);self.scroll.setWidgetResizable(False);self.setCentralWidget(self.scroll)
        self.build_toolbar();self.build_tools();self.build_layers();self.build_menu();self.style();self.refresh();self.canvas.sync()
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
        options.addWidget(QLabel('  Taille du pinceau  '));self.brush_size=QSpinBox();self.brush_size.setRange(1,400);self.brush_size.setValue(18);options.addWidget(self.brush_size)
        options.addSeparator();self.font=QFontComboBox();self.font.setFixedWidth(175);options.addWidget(self.font)
        self.text_size=QSpinBox();self.text_size.setRange(6,400);self.text_size.setValue(48);options.addWidget(self.text_size);options.addWidget(QLabel(' px · texte rasterisé  '))
        options.addSeparator();options.addAction(self.action('Annuler',self.undo,'Ctrl+Z'));options.addAction(self.action('Rétablir',self.redo,'Ctrl+Shift+Z'))
        options.addSeparator();options.addAction(self.action('Ajuster à la fenêtre',self.fit));options.addAction(self.action('100 %',lambda:self.set_zoom(1)))
        self.set_color(self.color)
    def build_tools(self):
        tb=QToolBar('Outils');tb.setMovable(False);tb.setOrientation(Qt.Vertical);self.addToolBar(Qt.LeftToolBarArea,tb)
        group=QActionGroup(self);group.setExclusive(True)
        for label,key,glyph in [('Déplacer','V','↔'),('Sélection','M','▧'),('Pinceau','B','✎'),('Gomme','E','▱'),('Texte','T','T'),('Rectangle','R','□'),('Ellipse','O','○'),('Pipette','I','◉'),('Remplir','G','▰'),('Recadrer','C','⌗')]:
            action=self.action(label,lambda checked=False,t=label:self.set_tool(t),key,True);action.setToolTip(f'{label} · {key}');group.addAction(action)
            name={'Déplacer':'move','Sélection':'select','Pinceau':'brush','Gomme':'eraser','Texte':'text','Rectangle':'rectangle','Ellipse':'ellipse','Pipette':'pipette','Remplir':'fill','Recadrer':'crop'}[label]
            action.setIcon(vector_icon(name,'#d5c9ff'));b=QToolButton();b.setDefaultAction(action);b.setToolButtonStyle(Qt.ToolButtonIconOnly);b.setIconSize(QSize(24,24));b.setFixedSize(44,44);b.setStyleSheet('padding:8px;');tb.addWidget(b)
            if label=='Pinceau':action.setChecked(True)
        self.tool_group=group
    def build_layers(self):
        dock=QDockWidget('Calques',self);dock.setFeatures(QDockWidget.NoDockWidgetFeatures);dock.setMinimumWidth(255);dock.setMaximumWidth(300)
        box=QWidget();layout=QVBoxLayout(box);layout.setContentsMargins(16,18,16,16);layout.setSpacing(12)
        caption=QLabel('Votre composition');caption.setObjectName('panelTitle');layout.addWidget(caption)
        hint=QLabel('Le calque du haut apparaît au premier plan.');hint.setWordWrap(True);hint.setObjectName('muted');layout.addWidget(hint)
        self.layers=QListWidget();self.layers.currentRowChanged.connect(self.layer_selected);self.layers.itemChanged.connect(self.visibility);self.layers.itemDoubleClicked.connect(self.rename);layout.addWidget(self.layers,1)
        layout.addWidget(QLabel('OPACITÉ'));self.opacity=QSpinBox();self.opacity.setRange(0,100);self.opacity.setSuffix(' %');self.opacity.valueChanged.connect(self.change_opacity);layout.addWidget(self.opacity)
        layout.addWidget(QLabel('MODE DE FUSION'));self.blend=QComboBox();self.blend.addItems(list(MODES));self.blend.currentTextChanged.connect(self.change_blend);layout.addWidget(self.blend)
        layout.addWidget(self.button('Ajouter un calque',lambda:self.add_layer(),True))
        row=QHBoxLayout()
        for label,fn in [('Monter',lambda:self.reorder(1)),('Descendre',lambda:self.reorder(-1))]:row.addWidget(self.button(label,fn))
        layout.addLayout(row)
        for label,fn in [('Dupliquer',self.duplicate),('Renommer',self.rename),('Supprimer',self.delete_layer)]:layout.addWidget(self.button(label,fn))
        note=QLabel('PNG conserve la transparence.\n.atelier conserve vos calques.');note.setObjectName('muted');layout.addWidget(note)
        dock.setWidget(box);self.addDockWidget(Qt.RightDockWidgetArea,dock)
    def build_menu(self):
        f=self.menuBar().addMenu('Fichier')
        for label,fn,key in [('Nouveau',self.new,'Ctrl+N'),('Ouvrir…',self.open,'Ctrl+O'),('Enregistrer',self.save,'Ctrl+S'),('Enregistrer sous…',lambda:self.save(True),'Ctrl+Shift+S'),('Importer un calque…',self.import_layer,None),('Exporter PNG / JPEG…',self.export,'Ctrl+Shift+E')]:f.addAction(self.action(label,fn,key))
        e=self.menuBar().addMenu('Édition');e.addAction(self.action('Annuler',self.undo));e.addAction(self.action('Rétablir',self.redo));e.addAction(self.action('Effacer la zone sélectionnée',self.clear_selection,'Delete'));e.addAction(self.action('Désélectionner',self.deselect,'Ctrl+D'))
        image=self.menuBar().addMenu('Image');image.addAction(self.action('Redimensionner…',self.resize_image));image.addAction(self.action('Rotation du calque à 90°',self.rotate));image.addAction(self.action('Miroir horizontal du calque',self.mirror))
        adjust=self.menuBar().addMenu('Réglages')
        for name in ['Luminosité','Contraste','Saturation','Netteté','Flou','Noir et blanc','Inverser les couleurs']:adjust.addAction(self.action(name,lambda checked=False,k=name:self.adjust(k)))
        view=self.menuBar().addMenu('Affichage');view.addAction(self.action('Ajuster à la fenêtre',self.fit));view.addAction(self.action('Zoom +',lambda:self.set_zoom(self.canvas.zoom*1.2),'Ctrl++'));view.addAction(self.action('Zoom −',lambda:self.set_zoom(self.canvas.zoom/1.2),'Ctrl+-'))
        help=self.menuBar().addMenu('Aide');help.addAction(self.action('À propos',lambda:QMessageBox.information(self,APP,'Atelier 0.1\n\nÉditeur raster local avec calques.\nSélection rectangulaire ; remplissage de toute la zone.\nTexte et formes rasterisés.\nRéglages appliqués au calque entier.\nPas de PSD, de masques ni de retouche avancée dans cette version.')))
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
        QToolTip{background:#353b4b;color:white;border:1px solid #656d84;padding:6px}''')
    def set_tool(self,tool):self.tool=tool;self.canvas.setCursor(Qt.CrossCursor if tool!='Déplacer' else Qt.SizeAllCursor);self.status()
    def set_color(self,color):self.color=QColor(color);self.color_button.setStyleSheet(f'background:{self.color.name()};color:{"#ffffff" if self.color.lightness()<160 else "#202020"};');self.color_button.setText(self.color.name().upper())
    def choose_color(self):
        from PySide6.QtWidgets import QColorDialog
        color=QColorDialog.getColor(self.color,self,'Couleur')
        if color.isValid():self.set_color(color)
    def status(self):
        p=self.project;self.setWindowTitle(f'{"● " if self.dirty else ""}{self.path.name if self.path else "Sans titre"} — Atelier')
        self.statusBar().showMessage(f'{p.width} × {p.height} px   ·   {round(self.canvas.zoom*100)} %   ·   {self.tool}   ·   {len(p.layers)} calque(s)   ·   '+('Modifications non enregistrées' if self.dirty else 'Prêt'))
    def modified(self):self.dirty=True;self.project.invalidate();self.canvas.update();self.status()
    def refresh(self):
        self.syncing=True;self.layers.clear()
        for l in reversed(self.project.layers):
            item=QListWidgetItem(l.name);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked if l.visible else Qt.Unchecked)
            pix=QPixmap.fromImage(l.image.scaled(38,30,Qt.KeepAspectRatio,Qt.SmoothTransformation));item.setIcon(QIcon(pix));self.layers.addItem(item)
        self.layers.setCurrentRow(len(self.project.layers)-1-self.project.active);self.opacity.setValue(self.project.layer.opacity);self.blend.setCurrentText(self.project.layer.mode);self.syncing=False;self.status();self.canvas.update()
    def layer_selected(self,row):
        if self.syncing or row<0:return
        self.project.active=len(self.project.layers)-1-row;self.refresh()
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
        if len(self.project.layers)>=100 or sum(l.image.width()*l.image.height()*4 for l in self.project.layers)+self.project.layer.image.width()*self.project.layer.image.height()*4>256*1024*1024:
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
    def fill(self):
        self.project.checkpoint();l=self.project.layer;p=QPainter(l.image);rect=self.canvas.selection or QRect(0,0,self.project.width,self.project.height);p.fillRect(rect.translated(-l.x,-l.y),self.color);p.end();self.modified()
    def clear_selection(self):
        self.project.checkpoint();l=self.project.layer;p=QPainter(l.image);p.setCompositionMode(QPainter.CompositionMode_Clear);p.fillRect((self.canvas.selection or QRect(0,0,self.project.width,self.project.height)).translated(-l.x,-l.y),Qt.transparent);p.end();self.modified()
    def add_text(self,pt):
        text,ok=QInputDialog.getMultiLineText(self,'Texte rasterisé','Texte (modifiable par Annuler avant d’autres opérations)')
        if not ok or not text:return
        if not self.io(lambda:self.project.add('Texte — '+text[:25])):return
        p=QPainter(self.project.layer.image);p.setRenderHint(QPainter.TextAntialiasing);font=self.font.currentFont();font.setPixelSize(self.text_size.value());p.setFont(font);p.setPen(self.color)
        p.drawText(QRect(pt.x(),pt.y(),max(1,self.project.width-pt.x()),max(1,self.project.height-pt.y())),Qt.AlignLeft|Qt.AlignTop|Qt.TextWordWrap,text);p.end();self.modified();self.refresh()
    def rotate(self):self.project.checkpoint();self.project.layer.image=self.project.layer.image.transformed(QTransform().rotate(90));self.modified();self.refresh()
    def mirror(self):self.project.checkpoint();self.project.layer.image=self.project.layer.image.mirrored(True,False);self.modified();self.refresh()
    def resize_image(self):
        w,ok=QInputDialog.getInt(self,'Redimensionner','Largeur en pixels',self.project.width,1,8192)
        if not ok:return
        h,ok=QInputDialog.getInt(self,'Redimensionner','Hauteur en pixels',round(w*self.project.height/self.project.width),1,8192)
        if ok:self.io(lambda:self.project.resize(w,h));self.modified();self.canvas.selection=None;self.canvas.sync();self.refresh()
    def adjust(self,kind):
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
    def replace_project(self,p,path=None):self.project=p;self.path=path;self.dirty=path is None;self.canvas.selection=None;self.refresh();self.canvas.sync();self.fit()
    def new(self):
        if not self.confirm():return
        w,ok=QInputDialog.getInt(self,'Nouveau document','Largeur en pixels',1000,1,8192)
        if not ok:return
        h,ok=QInputDialog.getInt(self,'Nouveau document','Hauteur en pixels',700,1,8192)
        if ok:
            p=self.io(lambda:Project(w,h))
            if p:self.replace_project(p)
    def open(self):
        if not self.confirm():return
        path,_=QFileDialog.getOpenFileName(self,'Ouvrir','','Images et projets (*.atelier *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)')
        if not path:return
        def perform():
            if Path(path).suffix.lower()=='.atelier':self.replace_project(Project.load(path),Path(path))
            else:
                image=load_image(path);p=Project(image.width(),image.height());p.layers=[Layer(Path(path).stem,image)];self.replace_project(p)
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
        try:self.project.save(path);self.path=path;self.dirty=False;self.recovery.unlink(missing_ok=True);self.status();return True
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
    def autosave(self):
        if self.dirty:
            try:self.project.save(self.recovery)
            except Exception as exc:self.statusBar().showMessage('Copie de secours impossible : '+str(exc))
    def offer_recovery(self):
        if self.recovery.exists():
            if QMessageBox.question(self,'Reprendre votre projet','Restaurer la copie de secours trouvée ?')==QMessageBox.Yes:
                p=self.io(lambda:Project.load(self.recovery))
                if p:self.replace_project(p)
            else:self.recovery.unlink(missing_ok=True)
    def closeEvent(self,event):
        if self.confirm():self.recovery.unlink(missing_ok=True);event.accept()
        else:event.ignore()


def main():
    app=QApplication(sys.argv);app.setApplicationName(APP);app.setOrganizationName(APP);app.setStyle('Fusion')
    if '--smoke-test' in sys.argv:
        QStandardPaths.setTestModeEnabled(True);app.setApplicationName('Atelier-smoke');w=Window();w.show();QTimer.singleShot(200,app.quit);return app.exec()
    from PySide6.QtNetwork import QLocalServer,QLocalSocket
    socket=QLocalSocket();socket.connectToServer('Atelier-local-editor')
    if socket.waitForConnected(200):QMessageBox.information(None,APP,'Atelier est déjà ouvert.');return 0
    QLocalServer.removeServer('Atelier-local-editor');server=QLocalServer();server.listen('Atelier-local-editor')
    w=Window();w.show();QTimer.singleShot(0,w.fit);return app.exec()

if __name__=='__main__':sys.exit(main())
