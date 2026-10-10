"""Raster layers, bounded undo history and atomic native project storage."""
import json
import os
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from PySide6.QtCore import Qt, QPoint, QRect, QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage, QPainter, QColor, QPen
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
    def copy(self):return Layer(self.name,QImage(self.image),self.visible,self.opacity,self.mode,self.x,self.y)


class Project:
    def __init__(self,w=1000,h=700):
        check_size(w,h);self.width=w;self.height=h
        self.layers=[Layer('Calque 1',blank(w,h))];self.active=0
        self.undo_stack=[];self.redo_stack=[];self.cache=None

    def state(self):return (self.width,self.height,self.active,[l.copy() for l in self.layers])
    def restore(self,state):
        self.width,self.height,self.active,layers=state;self.layers=[l.copy() for l in layers];self.invalidate()
    def checkpoint(self):
        self.undo_stack.append(self.state());self.redo_stack.clear()
        # Estimate full raster footprint; implicit Qt sharing reduces actual use.
        while len(self.undo_stack)>1 and (len(self.undo_stack)>20 or sum(sum(l.image.width()*l.image.height()*4 for l in st[3]) for st in self.undo_stack)>128*1024*1024):
            self.undo_stack.pop(0)
    def undo(self):
        if not self.undo_stack:return False
        self.redo_stack.append(self.state());self.restore(self.undo_stack.pop());return True
    def redo(self):
        if not self.redo_stack:return False
        self.undo_stack.append(self.state());self.restore(self.redo_stack.pop());return True
    def invalidate(self):self.cache=None
    @property
    def layer(self):return self.layers[self.active]
    def composite(self):
        if self.cache is None:
            self.cache=blank(self.width,self.height);p=QPainter(self.cache)
            for layer in self.layers:
                if layer.visible:
                    p.setOpacity(layer.opacity/100);p.setCompositionMode(MODES[layer.mode]);p.drawImage(layer.x,layer.y,layer.image)
            p.end()
        return self.cache
    def add(self,name,image=None):
        new_image=QImage(image) if image is not None else blank(self.width,self.height)
        if len(self.layers)>=100 or sum(l.image.width()*l.image.height()*4 for l in self.layers)+new_image.width()*new_image.height()*4>256*1024*1024:raise ValueError('Limite de 100 calques ou 256 Mo de pixels atteinte.')
        self.checkpoint();self.layers.append(Layer(name,new_image));self.active=len(self.layers)-1;self.invalidate();return True
    def stroke(self,a,b,color,size,erase=False,selection=None):
        l=self.layer;p=QPainter(l.image);p.setRenderHint(QPainter.Antialiasing)
        if selection is not None:p.setClipRect(selection.translated(-l.x,-l.y))
        p.setCompositionMode(QPainter.CompositionMode_Clear if erase else QPainter.CompositionMode_SourceOver)
        pen=QPen(QColor(color),size,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin);p.setPen(pen)
        p.drawLine(a-QPoint(l.x,l.y),b-QPoint(l.x,l.y));p.end();self.invalidate()
    def crop(self,rect):
        rect=rect.intersected(QRect(0,0,self.width,self.height))
        if rect.width()<1 or rect.height()<1:return False
        self.checkpoint()
        for l in self.layers:
            image=blank(rect.width(),rect.height());p=QPainter(image);p.drawImage(l.x-rect.x(),l.y-rect.y(),l.image);p.end();l.image=image;l.x=l.y=0
        self.width,self.height=rect.width(),rect.height();self.invalidate();return True
    def resize(self,w,h):
        check_size(w,h);sx=w/self.width;sy=h/self.height
        if sum(max(1,round(l.image.width()*sx))*max(1,round(l.image.height()*sy))*4 for l in self.layers)>256*1024*1024:raise ValueError("Cette taille dépasse la limite de 256 Mo de pixels.")
        self.checkpoint()
        for l in self.layers:
            l.image=l.image.scaled(max(1,round(l.image.width()*sx)),max(1,round(l.image.height()*sy)),Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
            l.x=round(l.x*sx);l.y=round(l.y*sy)
        self.width,self.height=w,h;self.invalidate()
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
        self.checkpoint();self.layer.image=QImage.fromData(output.getvalue()).convertToFormat(QImage.Format_ARGB32_Premultiplied);self.invalidate()
    def save(self,path):
        path=Path(path);fd,tmp=tempfile.mkstemp(dir=path.parent,suffix='.tmp');os.close(fd)
        try:
            manifest={'version':1,'width':self.width,'height':self.height,'active':self.active,'layers':[]}
            with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
                for i,l in enumerate(self.layers):
                    name=f'layers/{i}.png';z.writestr(name,png_bytes(l.image))
                    manifest['layers'].append({'name':l.name,'visible':l.visible,'opacity':l.opacity,'mode':l.mode,'x':l.x,'y':l.y,'file':name})
                z.writestr('project.json',json.dumps(manifest,ensure_ascii=False))
            os.replace(tmp,path)
        finally:Path(tmp).unlink(missing_ok=True)
    @classmethod
    def load(cls,path):
        with zipfile.ZipFile(path) as z:
            info=z.getinfo('project.json')
            if info.file_size>1000000:raise ValueError('Projet trop volumineux.')
            data=json.loads(z.read(info))
            if data.get('version')!=1:raise ValueError('Version de projet incompatible.')
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
                p.layers.append(Layer(item['name'],image.convertToFormat(QImage.Format_ARGB32_Premultiplied),item['visible'],item['opacity'],item['mode'],item['x'],item['y']))
            active=data.get('active',0)
            if type(active) is not int or not 0<=active<len(layers):raise ValueError('Calque actif invalide.')
            p.active=active;return p
