"""Raster layers, bounded undo history and atomic native project storage."""
import json
import copy
import os
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtCore import Qt, QPoint, QRect, QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage, QPainter, QColor, QPen, QPainterPath, QTransform, QFont, QFontMetrics
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

MAX_PIXELS = 16000000
MAX_EDGE = 8192
MODES = {'Normal':QPainter.CompositionMode_SourceOver, 'Produit':QPainter.CompositionMode_Multiply, 'Écran':QPainter.CompositionMode_Screen}


def check_size(w,h):
    if type(w) is not int or type(h) is not int or not (1 <= w <= MAX_EDGE and 1 <= h <= MAX_EDGE and w*h <= MAX_PIXELS):
        raise ValueError('Dimensions invalides : maximum 8192 px par côté et 16 millions de pixels.')


def blank(w,h):
    check_size(w,h)
    image = QImage(w,h,QImage.Format_ARGB32_Premultiplied); image.fill(Qt.transparent)
    return image


def png_bytes(image):
    data=QByteArray(); buf=QBuffer(data);buf.open(QIODevice.WriteOnly)
    if not image.save(buf,'PNG'):raise OSError('Image PNG impossible à encoder.')
    return bytes(data)


def load_image(path):
    from PySide6.QtGui import QImageReader
    reader=QImageReader(str(path));reader.setAutoTransform(True)
    size=reader.size();check_size(size.width(),size.height())
    image=reader.read()
    if image.isNull():raise ValueError('Image illisible : '+reader.errorString())
    return image.convertToFormat(QImage.Format_ARGB32_Premultiplied)


@dataclass
class Layer:
    name:str
    image:QImage
    visible:bool=True
    opacity:int=100
    mode:str='Normal'
    x:int=0
    y:int=0
    mask:QImage|None=None
    mask_enabled:bool=True
    locked:bool=False
    text:dict|None=None
    def copy(self):return Layer(self.name,QImage(self.image),self.visible,self.opacity,self.mode,self.x,self.y,QImage(self.mask) if self.mask is not None else None,self.mask_enabled,self.locked,copy.deepcopy(self.text))
    def effective(self):
        if self.mask is None or not self.mask_enabled:return self.image
        import io
        gray=Image.open(io.BytesIO(png_bytes(self.mask))).convert('L')
        alpha=Image.new('RGBA',gray.size,(255,255,255));alpha.putalpha(gray)
        data=alpha.tobytes();mask=QImage(data,gray.width,gray.height,QImage.Format_RGBA8888).copy()
        image=QImage(self.image);p=QPainter(image);p.setCompositionMode(QPainter.CompositionMode_DestinationIn);p.drawImage(0,0,mask);p.end();return image



class Project:
    def __init__(self,w=1000,h=700):
        check_size(w,h);self.width=w;self.height=h
        self.layers=[Layer('Calque 1',blank(w,h))];self.active=0
        self.undo_stack=[];self.redo_stack=[];self.undo_titles=[];self.redo_titles=[];self.cache=None

    def state(self):return (self.width,self.height,self.active,[l.copy() for l in self.layers])
    def restore(self,state):
        self.width,self.height,self.active,layers=state;self.layers=[l.copy() for l in layers];self.invalidate()
    def checkpoint(self,title="Modification"):
        self.undo_stack.append(self.state());self.undo_titles.append(title);self.redo_stack.clear();self.redo_titles.clear()
        # Estimate full raster footprint; implicit Qt sharing reduces actual use.
        while len(self.undo_stack)>1 and (len(self.undo_stack)>20 or sum(sum(l.image.width()*l.image.height()*4*(2 if l.mask is not None else 1) for l in st[3]) for st in self.undo_stack)>128*1024*1024):
            self.undo_stack.pop(0);self.undo_titles.pop(0)
    def undo(self):
        if not self.undo_stack:return False
        self.redo_stack.append(self.state());self.redo_titles.append(self.undo_titles.pop());self.restore(self.undo_stack.pop());return True
    def redo(self):
        if not self.redo_stack:return False
        self.undo_stack.append(self.state());self.undo_titles.append(self.redo_titles.pop());self.restore(self.redo_stack.pop());return True
    def invalidate(self):self.cache=None
    @property
    def layer(self):return self.layers[self.active]
    def composite(self):
        if self.cache is None:
            self.cache=blank(self.width,self.height);p=QPainter(self.cache)
            for layer in self.layers:
                if layer.visible:
                    p.setOpacity(layer.opacity/100);p.setCompositionMode(MODES[layer.mode]);p.drawImage(layer.x,layer.y,layer.effective())
            p.end()
        return self.cache
    def add(self,name,image=None):
        new_image=QImage(image) if image is not None else blank(self.width,self.height)
        if len(self.layers)>=100 or sum(l.image.width()*l.image.height()*4*(2 if l.mask is not None else 1) for l in self.layers)+new_image.width()*new_image.height()*4>256*1024*1024:raise ValueError('Limite de 100 calques ou 256 Mo de pixels atteinte.')
        self.checkpoint("Ajouter un calque");self.layers.append(Layer(name,new_image));self.active=len(self.layers)-1;self.invalidate();return True
    def stroke(self,a,b,color,size,erase=False,selection=None,on_mask=False):
        l=self.layer
        if l.locked:return
        if on_mask and l.mask is None:return
        if not on_mask:l.text=None
        p=QPainter(l.mask if on_mask else l.image);p.setRenderHint(QPainter.Antialiasing)
        if selection is not None:
            if isinstance(selection,QPainterPath):p.setClipPath(QTransform().translate(-l.x,-l.y).map(selection))
            else:p.setClipRect(selection.translated(-l.x,-l.y))
        if on_mask:
            value=QColor(color).lightness();color=QColor(value,value,value)
            erase=False
        p.setCompositionMode(QPainter.CompositionMode_Clear if erase else QPainter.CompositionMode_SourceOver)
        pen=QPen(QColor(color),size,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin);p.setPen(pen)
        p.drawLine(a-QPoint(l.x,l.y),b-QPoint(l.x,l.y));p.end();self.invalidate()
    def crop(self,rect):
        rect=rect.intersected(QRect(0,0,self.width,self.height))
        if rect.width()<1 or rect.height()<1:return False
        self.checkpoint()
        for l in self.layers:
            image=blank(rect.width(),rect.height());p=QPainter(image);p.drawImage(l.x-rect.x(),l.y-rect.y(),l.image);p.end()
            if l.mask is not None:
                mask=blank(rect.width(),rect.height());mask.fill(Qt.black);p=QPainter(mask);p.drawImage(l.x-rect.x(),l.y-rect.y(),l.mask);p.end();l.mask=mask
            l.image=image;l.x=l.y=0;l.text=None
        self.width,self.height=rect.width(),rect.height();self.invalidate();return True
    def resize(self,w,h):
        check_size(w,h);sx=w/self.width;sy=h/self.height
        if sum(max(1,round(l.image.width()*sx))*max(1,round(l.image.height()*sy))*4*(2 if l.mask is not None else 1) for l in self.layers)>256*1024*1024:raise ValueError("Cette taille dépasse la limite de 256 Mo de pixels.")
        self.checkpoint()
        for l in self.layers:
            l.image=l.image.scaled(max(1,round(l.image.width()*sx)),max(1,round(l.image.height()*sy)),Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
            if l.mask is not None:l.mask=l.mask.scaled(l.image.size(),Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
            l.x=round(l.x*sx);l.y=round(l.y*sy);l.text=None
        self.width,self.height=w,h;self.invalidate()
    def add_mask(self,selection=None):
        if self.layer.mask is not None:return False
        if sum(l.image.width()*l.image.height()*4*(2 if l.mask is not None else 1) for l in self.layers)+self.layer.image.width()*self.layer.image.height()*4>256*1024*1024:raise ValueError('Budget de pixels dépassé.')
        self.checkpoint("Masque de calque");l=self.layer;l.mask=blank(l.image.width(),l.image.height());l.mask.fill(Qt.white if selection is None else Qt.black)
        if selection is not None:
            painter=QPainter(l.mask);painter.setPen(Qt.NoPen);painter.setBrush(Qt.white)
            if isinstance(selection,QPainterPath):painter.drawPath(QTransform().translate(-l.x,-l.y).map(selection))
            else:painter.drawRect(selection.translated(-l.x,-l.y))
            painter.end()
        self.invalidate();return True
    def transform_layer(self,w,h,angle=0):
        check_size(w,h)
        if self.layer.locked:raise ValueError('Le calque est verrouillé.')
        image=self.layer.image.scaled(w,h,Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
        transform=QTransform().rotate(angle);image=image.transformed(transform,Qt.SmoothTransformation);check_size(image.width(),image.height())
        budget=sum(l.image.width()*l.image.height()*4*(2 if l.mask is not None else 1) for l in self.layers if l is not self.layer)+image.width()*image.height()*4*(2 if self.layer.mask is not None else 1)
        if budget>256*1024*1024:raise ValueError('Budget de pixels dépassé.')
        self.checkpoint("Transformation");l=self.layer;l.image=image
        if l.mask is not None:l.mask=l.mask.scaled(w,h,Qt.IgnoreAspectRatio,Qt.SmoothTransformation).transformed(transform,Qt.SmoothTransformation)
        l.text=None;self.invalidate();return True
    def render_text(self,spec):
        font=QFont(spec['family']);font.setPixelSize(spec['size'])
        metrics=QFontMetrics(font);lines=spec['content'].split('\n')
        w=max(1,max(metrics.horizontalAdvance(line) for line in lines)+12);h=max(1,metrics.lineSpacing()*len(lines)+12);check_size(w,h)
        image=blank(w,h);painter=QPainter(image);painter.setRenderHint(QPainter.TextAntialiasing);painter.setFont(font);painter.setPen(QColor(spec['color']))
        for i,line in enumerate(lines):painter.drawText(6,6+metrics.ascent()+i*metrics.lineSpacing(),line)
        painter.end();return image
    def set_text(self,spec,new=False,x=0,y=0):
        image=self.render_text(spec)
        if new:
            self.add('Texte — '+spec['content'][:25],image);self.layer.x=x;self.layer.y=y
        else:
            if self.layer.locked:raise ValueError('Le calque est verrouillé.')
            budget=sum(l.image.width()*l.image.height()*4*(2 if l.mask is not None else 1) for l in self.layers if l is not self.layer)+image.width()*image.height()*4*(2 if self.layer.mask is not None else 1)
            if budget>256*1024*1024:raise ValueError('Budget de pixels dépassé.')
            self.checkpoint("Modifier le texte");self.layer.image=image
            if self.layer.mask is not None:self.layer.mask=self.layer.mask.scaled(image.size(),Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
        self.layer.text=copy.deepcopy(spec);self.invalidate();return True
    def adjust(self,kind,value=1.0):
        import io
        source=Image.open(io.BytesIO(png_bytes(self.layer.image))).convert('RGBA');alpha=source.getchannel('A');rgb=source.convert('RGB')
        if kind=='Luminosité':rgb=ImageEnhance.Brightness(rgb).enhance(value)
        elif kind=='Contraste':rgb=ImageEnhance.Contrast(rgb).enhance(value)
        elif kind=='Saturation':rgb=ImageEnhance.Color(rgb).enhance(value)
        elif kind=='Netteté':rgb=ImageEnhance.Sharpness(rgb).enhance(value)
        elif kind=='Flou':rgb=rgb.filter(ImageFilter.GaussianBlur(value))
        elif kind=='Noir et blanc':rgb=ImageOps.grayscale(rgb).convert('RGB')
        elif kind=='Inverser les couleurs':rgb=ImageOps.invert(rgb)
        else:raise ValueError('Réglage inconnu.')
        rgb.putalpha(alpha);output=io.BytesIO();rgb.save(output,format='PNG')
        self.checkpoint(kind);self.layer.text=None;self.layer.image=QImage.fromData(output.getvalue()).convertToFormat(QImage.Format_ARGB32_Premultiplied);self.invalidate()
    def save(self,path):
        path=Path(path);fd,tmp=tempfile.mkstemp(dir=path.parent,suffix='.tmp');os.close(fd)
        try:
            manifest={'version':2,'width':self.width,'height':self.height,'active':self.active,'layers':[]}
            with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
                for i,l in enumerate(self.layers):
                    name=f'layers/{i}.png';z.writestr(name,png_bytes(l.image))
                    entry={'name':l.name,'visible':l.visible,'opacity':l.opacity,'mode':l.mode,'x':l.x,'y':l.y,'file':name,'locked':l.locked,'mask_enabled':l.mask_enabled,'text':l.text}
                    if l.mask is not None:
                        entry['mask']=f'layers/{i}-mask.png';z.writestr(entry['mask'],png_bytes(l.mask))
                    manifest['layers'].append(entry)
                z.writestr('project.json',json.dumps(manifest,ensure_ascii=False))
            os.replace(tmp,path)
        finally:Path(tmp).unlink(missing_ok=True)
    @classmethod
    def load(cls,path):
        with zipfile.ZipFile(path) as z:
            info=z.getinfo('project.json')
            if info.file_size>1000000:raise ValueError('Projet trop volumineux.')
            data=json.loads(z.read(info))
            if data.get('version') not in (1,2):raise ValueError('Version de projet incompatible.')
            check_size(data['width'],data['height'])
            layers=data.get('layers')
            if not isinstance(layers,list) or not 1<=len(layers)<=100:raise ValueError('Liste de calques invalide.')
            p=cls(data['width'],data['height']);p.layers=[]
            total=0
            for item in layers:
                if not isinstance(item.get('name'),str) or type(item.get('opacity')) is not int or not 0<=item['opacity']<=100 or item.get('mode') not in MODES or type(item.get('visible')) is not bool:raise ValueError('Calque invalide.')
                if any(type(item.get(k)) is not int or abs(item[k])>MAX_EDGE*2 for k in ('x','y')):raise ValueError('Position de calque invalide.')
                info=z.getinfo(item['file'])
                if info.file_size>100000000:raise ValueError('Calque trop volumineux.')
                from PySide6.QtGui import QImageReader
                raw=QByteArray(z.read(info));buf=QBuffer(raw);buf.open(QIODevice.ReadOnly);reader=QImageReader(buf,b'PNG');size=reader.size();check_size(size.width(),size.height())
                total+=size.width()*size.height()*4
                if total>256*1024*1024:raise ValueError('Le projet dépasse 256 Mo de pixels.')
                image=reader.read()
                if image.isNull():raise ValueError('Calque endommagé.')
                layer=Layer(item['name'],image.convertToFormat(QImage.Format_ARGB32_Premultiplied),item['visible'],item['opacity'],item['mode'],item['x'],item['y'])
                if 'mask' in item:
                    mi=z.getinfo(item['mask'])
                    if mi.file_size>100000000:raise ValueError('Masque trop volumineux.')
                    raw=QByteArray(z.read(mi));buf=QBuffer(raw);buf.open(QIODevice.ReadOnly);mr=QImageReader(buf,b'PNG')
                    if mr.size()!=image.size():raise ValueError('Dimensions de masque invalides.')
                    layer.mask=mr.read().convertToFormat(QImage.Format_ARGB32_Premultiplied)
                    if layer.mask.isNull():raise ValueError('Masque illisible.')
                    total+=image.width()*image.height()*4
                    if total>256*1024*1024:raise ValueError('Le projet dépasse 256 Mo de pixels.')
                for key in ('locked','mask_enabled'):
                    if key in item and type(item[key]) is not bool:raise ValueError('Propriété de calque invalide.')
                layer.locked=item.get('locked',False);layer.mask_enabled=item.get('mask_enabled',True)
                spec=item.get('text')
                if spec is not None:
                    if not isinstance(spec,dict) or not isinstance(spec.get('content'),str) or len(spec['content'])>10000 or not isinstance(spec.get('family'),str) or len(spec['family'])>256 or type(spec.get('size')) is not int or not 6<=spec['size']<=400 or not isinstance(spec.get('color'),str) or not QColor(spec['color']).isValid():raise ValueError('Texte invalide.')
                    layer.text=spec
                p.layers.append(layer)
            active=data.get('active',0)
            if type(active) is not int or not 0<=active<len(layers):raise ValueError('Calque actif invalide.')
            p.active=active;return p
