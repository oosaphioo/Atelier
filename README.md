# Atelier 0.1 — éditeur d’images pour Windows

Première version de notre logiciel de création et de retouche d’images.
Interface française, thème sombre, usage hors connexion, sans compte.
**Cette version est une base fonctionnelle ; elle n’équivaut pas à Photoshop.**

## Installation via GitHub

1. Décompressez l’archive, puis ouvrez le dossier **Atelier** dans Visual Studio Code.
2. Publiez **le contenu de ce dossier dans un nouveau dépôt**, séparé de Plume.
   `main.py`, `model.py`, `icons.py`, `requirements.txt` et `.github` doivent être
   à la racine. Le dossier `.github` contient le fichier de compilation Windows.
3. Ouvrez **Actions → Construire Atelier pour Windows**. Le workflow démarre
   sur main/master ; sinon utilisez **Run workflow**.
4. Attendez la coche verte. Dans **Summary → Artifacts**, téléchargez
   **Atelier-Installation-Windows**.
5. Décompressez le téléchargement, puis lancez **Atelier-Installation-Windows.exe**.

L’installateur est prévu pour Windows 10/11 64 bits. Il n’est pas encore compilé
ici : ce projet a été testé sous Linux avec Qt. GitHub exécutera les tests sur
Windows et vérifiera le démarrage de l’exécutable avant de produire l’installateur.
L’installateur est sans signature d’éditeur. Une version portable est également
produite : gardez tous ses fichiers ensemble.

## Outils disponibles

- **Déplacer (V)** : déplace le calque actif en glissant sur l’image.
- **Sélection (M)** : sélection rectangulaire ; contraint pinceau, gomme,
  rectangle, ellipse, effacement et remplissage.
- **Pinceau (B)** : dessine sur le calque actif, couleur et taille réglables.
- **Gomme (E)** : efface jusqu’à la transparence sur le calque actif.
- **Texte (T)** : cliquez dans l’image, saisissez votre texte. Un calque dédié
  est créé avec la police et la taille en pixels choisies.
- **Rectangle (R) / Ellipse (O)** : contours tracés par glissement ; épaisseur
  définie par la taille du pinceau.
- **Pipette (I)** : prend la couleur de la composition visible.
- **Remplir (G)** : remplit toute la sélection, ou toute la zone du document
  sur le calque actif. Ce n’est pas encore un pot de peinture par contiguïté.
- **Recadrer (C)** : tracez une zone et confirmez. Tous les calques sont recadrés.
- **Suppr** : efface la sélection, ou la zone du document sur le calque actif.
- **Ctrl+D** : retire la sélection.

Les opérations restent possibles sur un calque masqué ; cochez sa case pour
voir votre travail. Les réglages et transformations s’appliquent au calque actif
entier, même si une sélection est affichée.

## Calques et retouche

Ajoutez, importez, dupliquez, renommez et réordonnez les calques. Le premier
calque dans la liste est au-dessus des autres. Case cochée = calque visible.
Opacité de 0 à 100 %. Modes de fusion : Normal, Produit et Écran.
Les grandes images importées comme calques sont réduites pour tenir dans
le document ; utilisez Ouvrir pour conserver les dimensions originales.

Menu **Réglages** : luminosité, contraste, saturation, netteté, flou,
noir et blanc, inversion. Ces réglages modifient les pixels du calque actif ;
**Ctrl+Z** permet de revenir en arrière. Le canal alpha est conservé.
Le flou de cette version agit sur les couleurs et conserve la forme alpha.

Menu **Image** : redimensionnement du document entier, rotation du calque de
90° et miroir horizontal. La rotation ne modifie pas la taille du document :
une partie du calque peut dépasser. Déplacez-le pour la retrouver.

**Annuler : Ctrl+Z. Rétablir : Ctrl+Shift+Z.**
L’historique est limité à 20 états avec un budget indicatif de 128 Mo.
Il n’est pas enregistré dans les fichiers de projet.

## Enregistrement et transparence

- **.atelier** : conserve tous les calques, pixels, visibilité, opacité,
  positions, dimensions et modes de fusion. Enregistrez avec **Ctrl+S**.
- **PNG** : export aplati avec transparence. Le damier est un repère visuel ;
  il n’est jamais ajouté au fichier.
- **JPEG** : export aplati, les parties transparentes deviennent blanches.
- Images ouvertes : PNG, JPEG, WebP, BMP et TIFF, selon les codecs disponibles.
  Orientation photo appliquée lors de l’ouverture.

Une copie de secours locale du projet modifié est écrite toutes les 30 secondes.
Elle est proposée au prochain lancement après une interruption. Elle ne remplace
pas Ctrl+S et peut perdre les 30 dernières secondes. Une seule instance est autorisée.

Zoom : **Ctrl + molette**, boutons **100 % / Ajuster à la fenêtre**, ou Ctrl+/Ctrl−.
Les barres de défilement permettent de naviguer dans l’image agrandie.

## Limites de la première version

Pas encore de PSD, RAW, masques, courbes, niveaux, baguette magique, lasso,
retouche locale, tampon, détourage automatique, CMJN, profils ICC, objets
vectoriels ou dynamiques, pinceaux avancés ni réglages non destructifs.
Les textes et formes deviennent des pixels ; le texte ne se réédite pas
comme un texte Photoshop. Les images exportées sont aplaties.
Pas de gestion colorimétrique : utilisez cette version pour les créations écran,
pas pour une chaîne de production destinée à l’impression professionnelle.
Limites : 8192 pixels par côté, 16 millions de pixels par document,
100 calques et 256 Mo de données pixels cumulées dans un projet.

## Développement local

Python 3.12. Double-cliquez **Lancer-Atelier.cmd** pour installer les dépendances
la première fois et lancer l’application. La première installation nécessite
Internet ; l’application reste locale ensuite.

**Construire-Windows.cmd** produit une version portable ; Inno Setup 6 permet
également de fabriquer l’installateur.

```sh
python -m pip install -r requirements.txt
python main.py
python -m unittest discover -s tests -v
```

7 tests couvrent la composition des calques, visibilité/opacité, gomme et
sélection, annuler/rétablir, projets multicouches, recadrage, alpha des réglages,
PNG transparent et gestes de dessin dans l’interface avec copie de secours.
