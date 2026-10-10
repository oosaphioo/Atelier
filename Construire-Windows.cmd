import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint,QRect,Qt,QStandardPaths
from PySide6.QtGui import QColor,QPainter,QFont
from PySide6.QtTest import QTest
from model import Project,Layer,blank
from main import Window
app=QApplication.instance() or QApplication([]);app.setApplicationName('Atelier-tests');QStandardPaths.setTestModeEnabled(True)

class EngineTests(unittest.TestCase):
    def test_compositing_opacity_visibility_offset(self):
        p=Project(20,20);p.layers[0].image.fill(QColor('red'))
        image=blank(10,10);image.fill(QColor('blue'));p.add('Bleu',image);p.layer.x=5;p.layer.y=5;p.layer.opacity=50;p.invalidate()
        c=p.composite().pixelColor(8,8);self.assertAlmostEqual(c.red(),128,delta=1);self.assertAlmostEqual(c.blue(),128,delta=1)
        self.assertEqual(p.composite().pixelColor(0,0),QColor('red'))
        p.layer.visible=False;p.invalidate();self.assertEqual(p.composite().pixelColor(8,8),QColor('red'))
    def test_eraser_selection_and_undo_redo(self):
        p=Project(40,40);p.layers[0].image.fill(QColor('red'));p.checkpoint()
        p.stroke(QPoint(2,20),QPoint(38,20),'blue',10,True,QRect(10,10,20,20))
        self.assertEqual(p.layer.image.pixelColor(20,20).alpha(),0)
        self.assertEqual(p.layer.image.pixelColor(5,20).alpha(),255)
        p.undo();self.assertEqual(p.layer.image.pixelColor(20,20).alpha(),255)
        p.redo();self.assertEqual(p.layer.image.pixelColor(20,20).alpha(),0)
    def test_native_roundtrip_and_crop(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Project(20,20);p.add('Décor');p.layer.image.fill(QColor('green'));p.layer.x=4;p.layer.opacity=71;p.layer.mode='Produit'
            path=Path(tmp)/'test.atelier';p.save(path);q=Project.load(path)
            self.assertEqual(q.layer.name,'Décor');self.assertEqual(q.layer.opacity,71);self.assertEqual(q.layer.x,4);self.assertEqual(q.layer.mode,'Produit')
            self.assertEqual(p.composite(),q.composite())
            q.crop(QRect(3,3,10,10));self.assertEqual((q.width,q.height),(10,10));self.assertEqual(q.layer.x,0)
            q.undo();self.assertEqual(q.width,20);self.assertEqual(q.layer.x,4)
    def test_adjustments_preserve_alpha_and_undo(self):
        p=Project(5,5);p.layer.image.fill(QColor(100,50,25,128));p.adjust('Noir et blanc')
        c=p.layer.image.pixelColor(0,0);self.assertEqual(c.alpha(),128);self.assertAlmostEqual(c.red(),c.blue(),delta=1)
        p.undo();self.assertGreater(p.layer.image.pixelColor(0,0).red(),p.layer.image.pixelColor(0,0).blue())
    def test_invalid_and_oversized_projects(self):
        with self.assertRaises(ValueError):Project(8192,8192)
        with self.assertRaises(ValueError):Project(-1,100)
    def test_png_transparency(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Project(40,40);p.stroke(QPoint(10,10),QPoint(20,20),'blue',3)
            path=Path(tmp)/'export.png';self.assertTrue(p.composite().save(str(path),'PNG'))
            from model import load_image
            self.assertEqual(load_image(path).pixelColor(0,0).alpha(),0)

class InterfaceTests(unittest.TestCase):
    def test_paint_undo_layers_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            w=Window();w.timer.stop();w.recovery=Path(tmp)/'recovery.atelier';w.show();app.processEvents();w.set_zoom(.5);app.processEvents()
            QTest.mousePress(w.canvas,Qt.LeftButton,Qt.NoModifier,QPoint(70,70));QTest.mouseMove(w.canvas,QPoint(120,100));QTest.mouseRelease(w.canvas,Qt.LeftButton,Qt.NoModifier,QPoint(120,100))
            self.assertTrue(w.dirty);self.assertFalse(w.project.layer.image.pixelColor(76,76).alpha()==0)
            w.undo();self.assertEqual(w.project.layer.image.pixelColor(76,76).alpha(),0);w.redo()
            w.add_layer();self.assertEqual(len(w.project.layers),2);w.autosave();self.assertEqual(len(Project.load(w.recovery).layers),2)
            w.dirty=False;w.close()



class VersionTwoTests(unittest.TestCase):
    def test_mask_hides_without_destroying_and_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Project(40,40);p.layer.image.fill(QColor('red'));p.add_mask()
            p.checkpoint();p.stroke(QPoint(8,20),QPoint(30,20),'black',10,on_mask=True)
            self.assertEqual(p.composite().pixelColor(20,20).alpha(),0)
            self.assertEqual(p.layer.image.pixelColor(20,20).alpha(),255)
            path=Path(tmp)/'masked.atelier';p.save(path);q=Project.load(path)
            self.assertEqual(q.composite(),p.composite());q.layer.mask_enabled=False;q.invalidate();self.assertEqual(q.composite().pixelColor(20,20).alpha(),255)
            p.undo();self.assertEqual(p.composite().pixelColor(20,20).alpha(),255)
    def test_lasso_clips_and_mask_resizes(self):
        from PySide6.QtGui import QPainterPath
        p=Project(40,40);path=QPainterPath();path.moveTo(10,10);path.lineTo(30,10);path.lineTo(20,30);path.closeSubpath()
        p.stroke(QPoint(0,20),QPoint(39,20),'red',3,selection=path)
        self.assertGreater(p.layer.image.pixelColor(20,20).alpha(),0);self.assertEqual(p.layer.image.pixelColor(2,20).alpha(),0)
        p.add_mask(path);p.transform_layer(20,20,90)
        self.assertEqual(p.layer.mask.size(),p.layer.image.size());p.undo();self.assertEqual(p.layer.image.width(),40)
    def test_editable_text_and_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Project(300,100);spec={'content':'Bonjour','family':'DejaVu Sans','size':24,'color':'#ff0000'};p.set_text(spec,True,10,20)
            self.assertEqual(p.layer.x,10);self.assertEqual(p.layer.text['content'],'Bonjour')
            spec['content']='Au revoir';p.set_text(spec);p.undo();self.assertEqual(p.layer.text['content'],'Bonjour')
            path=Path(tmp)/'text.atelier';p.save(path);q=Project.load(path);self.assertEqual(q.layer.text['content'],'Bonjour')
            q.layer.locked=True;before=q.layer.image.copy();q.stroke(QPoint(1,1),QPoint(30,30),'black',10);self.assertEqual(q.layer.image,before)
            with self.assertRaises(ValueError):q.transform_layer(50,50)
    def test_multiple_documents_and_selection_copy(self):
        from PySide6.QtGui import QPainterPath
        w=Window();w.timer.stop();w.project.layer.image.fill(QColor('red'));w.modified();first=w.project
        w.open_session(Project(80,60));self.assertEqual(len(w.sessions),2);w.project.layer.image.fill(QColor('blue'));w.modified()
        w.tabs.setCurrentIndex(0);self.assertIs(w.project,first);self.assertTrue(w.dirty);self.assertEqual(w.project.layer.image.pixelColor(0,0),QColor('red'))
        path=QPainterPath();path.addEllipse(QRect(10,10,30,30));w.canvas.selection=path;w.selection_to_layer();self.assertEqual(len(w.project.layers),2);self.assertEqual(w.project.layer.x,10)
        self.assertEqual(w.project.layer.image.pixelColor(0,0).alpha(),0);self.assertEqual(w.project.layer.image.pixelColor(15,15).alpha(),255)
        for s in w.sessions:s['dirty']=False
        w.dirty=False;w.store_session();w.close()
    def test_corner_transform_undo(self):
        w=Window();w.timer.stop();w.project=Project(200,150);image=blank(60,40);image.fill(QColor('green'));w.project.add('Objet',image);w.project.layer.x=20;w.project.layer.y=20;w.refresh();w.show();app.processEvents();w.set_zoom(1)
        w.set_tool('Transformer');QTest.mousePress(w.canvas,Qt.LeftButton,Qt.NoModifier,QPoint(111,91));QTest.mouseMove(w.canvas,QPoint(151,111));QTest.mouseRelease(w.canvas,Qt.LeftButton,Qt.NoModifier,QPoint(151,111))
        self.assertGreater(w.project.layer.image.width(),60);w.undo();self.assertEqual(w.project.layer.image.width(),60)
        w.dirty=False;w.store_session();w.close()

class RecoveryTests(unittest.TestCase):
    def test_workspace_restores_all_documents(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QMessageBox
        with tempfile.TemporaryDirectory() as tmp:
            w=Window();w.timer.stop();w.recovery=Path(tmp)/'recovery.atelier';w.project.layer.image.fill(QColor('red'));w.modified()
            w.open_session(Project(20,20));w.project.layer.image.fill(QColor('blue'));w.modified();w.autosave()
            recovered=Window();recovered.timer.stop();recovered.recovery=w.recovery
            with patch('main.QMessageBox.question',return_value=QMessageBox.Yes):recovered.offer_recovery()
            self.assertEqual(len(recovered.sessions),2)
            recovered.tabs.setCurrentIndex(0);self.assertEqual(recovered.project.layer.image.pixelColor(0,0),QColor('red'))
            recovered.tabs.setCurrentIndex(1);self.assertEqual(recovered.project.layer.image.pixelColor(0,0),QColor('blue'))
            for win in (w,recovered):
                for state in win.sessions:state['dirty']=False
                win.dirty=False;win.store_session();win.close()

if __name__=='__main__':unittest.main()
