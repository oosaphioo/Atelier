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

if __name__=='__main__':unittest.main()
