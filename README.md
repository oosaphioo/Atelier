# Atelier 0.2 — un espace de création plus familier

Éditeur d’images Windows en français, local, sans compte ni abonnement.
Cette version rapproche les gestes de travail de ceux d’un grand éditeur photo :
barre d’outils verticale, options contextuelles, onglets et panneaux de calques.
**Atelier n’a pas encore toutes les fonctions ni la puissance de Photoshop.**

## Mise à jour depuis Atelier 0.1

1. Fermez Atelier et sauvegardez vos fichiers de projet.
2. Remplacez les fichiers de votre dossier de développement par ceux de cette archive.
   Conservez votre dossier `.git` et vos documents personnels.
3. Dans Visual Studio Code : validez les modifications, puis synchronisez avec GitHub.
4. Dans **Actions → Construire Atelier pour Windows → Summary → Artifacts**,
   téléchargez le nouvel installateur après la coche verte.
5. Installez-le au même endroit. L’icône violette avec pinceau apparaît maintenant
   sur l’application, l’exécutable et les nouveaux raccourcis.

Les projets de la version 0.1 s’ouvrent dans 0.2. Les nouveaux fichiers avec masques
et texte modifiable nécessitent 0.2 : l’ancienne version ne les lit pas.
L’installateur Windows sera compilé par GitHub ; il n’a pas été compilé ici.

Pour une première installation, publiez le contenu du dossier **Atelier** à la
racine d’un nouveau dépôt GitHub, distinct de Plume. Gardez `main.py`, `model.py`,
`icons.py`, `requirements.txt`, `assets` et `.github` ensemble à la racine.
Le guide GitHub de Plume s’applique : Actions, coche verte, puis Artifacts.
L’installateur reste sans signature d’éditeur.

## Les nouveautés

### Documents et navigation

Ouvrez plusieurs documents dans des onglets. Chacun conserve ses calques,
ses modifications, sa sélection, son zoom et son historique. Une croix ferme
l’onglet en proposant d’enregistrer. Jusqu’à 20 documents simultanés.

**Espace + glisser** ou bouton central de la souris : déplacer la vue.
**Ctrl + molette** : zoom. Pour la touche Espace, cliquez d’abord dans l’image.
La barre supérieure montre la taille du pinceau pour les outils de dessin,
et la police/taille pour l’outil texte. Les infobulles expliquent chaque outil.

### Masques de calque

Sélectionnez un calque, puis cliquez **Ajouter un masque**. Si une sélection
est présente, le masque révèle cette sélection et cache le reste ; sinon il
révèle tout. Les pixels d’origine restent intacts.

Cochez **Modifier le masque**. Utilisez le pinceau avec :
- **Noir** pour cacher ;
- **Blanc** pour révéler ;
- **Gris** pour une transparence intermédiaire.

Décochez Modifier le masque pour revenir aux pixels du calque. Le masque
suit le calque lors des déplacements et transformations. **Activer le masque**
permet de comparer avant/après. **Retirer** enlève le masque en révélant les
pixels cachés. Ces opérations sont annulables et enregistrées dans le projet.

### Transformations

**Ctrl+T** active les poignées sur le calque. Glissez un coin pour changer sa
taille ; maintenez **Maj** pour conserver les proportions. Glissez ailleurs
pour déplacer le calque. **Échap** annule une transformation en cours de glissement.
Relâcher la souris valide : le redimensionnement modifie les pixels et peut être
annulé avec Ctrl+Z.

Le panneau **Propriétés & historique** (onglet en bas à droite), ou le menu
**Image → Transformer le calque…**, donne largeur, hauteur, angle et position.
La boîte affiche un aperçu du calque, sans modifier le projet avant validation.
Une transformation géométrique rasterise un texte modifiable, après indication
ou confirmation selon l’outil. La taille du document ne change pas.

### Sélections et extraction

- **M** : rectangle.
- **L** : lasso tracé à main levée ; il se referme au relâchement.
- **Ctrl+D** : retirer la sélection.
- **Ctrl+J** : copier les pixels visibles du calque actif dans la sélection
  sur un nouveau calque, placé au même endroit. Le masque est pris en compte.
- **Suppr** : effacer dans la sélection, ou dans la zone du document sans sélection.

La sélection contraint le pinceau, la gomme, les formes, le remplissage et
l’effacement. Les réglages de couleur affectent toujours le calque entier.

### Texte modifiable

Choisissez **T**, cliquez dans l’image, puis saisissez le texte, sa police,
sa taille en pixels et sa couleur. Un calque texte dédié est ajouté.
Double-cliquez sur son nom dans la liste, sur l’image lorsque ce calque est
actif, ou utilisez **Édition → Modifier le texte** pour le rééditer.

Le contenu et les paramètres restent modifiables après sauvegarde/réouverture.
Peindre sur le texte exige de le rasteriser avec confirmation. Redimensionner
le document entier, recadrer, appliquer un réglage ou transformer le texte
le convertit en pixels. Annuler restaure le texte modifiable.

### Verrouillage et historique

**Verrouiller le calque** bloque le dessin, le déplacement, la modification du
texte et les transformations du calque. Les opérations sur le document entier
comme le recadrage restent globales.

Le panneau **Propriétés & historique** affiche les états conservés. Cliquez
sur un état antérieur pour revenir en arrière. **Ctrl+Z** annule et
**Ctrl+Shift+Z** rétablit. L’historique est limité à 20 étapes et environ
128 Mo de données pixels estimées ; il n’est pas enregistré dans le projet.

## Outils de la version précédente

Pinceau (B), gomme (E), déplacement (V), pipette (I), remplissage (G), rectangles
(R), ellipses (O), recadrage (C), import de calques et duplication/réorganisation.
Les formes sont des contours ; le remplissage affecte toute la sélection ou
la zone du document, pas une région de pixels contigus.

Réglages : luminosité, contraste, saturation, netteté, flou, noir et blanc et
inversion. Ils modifient les pixels et restent annulables. Le flou conserve
la forme alpha. Rotation 90° et miroir horizontal du calque disponibles.

## Fichiers, exports et copies de secours

- **Ctrl+S / .atelier** conserve calques, masques, texte, positions, verrouillages,
  visibilité, opacité et modes de fusion.
- **PNG** exporte la composition aplatie avec transparence ; le damier n’est
  jamais ajouté au fichier.
- **JPEG** exporte une composition aplatie sur fond blanc.
- Ouverture : PNG, JPEG, WebP, BMP, TIFF selon les codecs disponibles, et .atelier.
- Normal, Produit et Écran sont les trois modes de fusion actuellement disponibles.

Toutes les 30 secondes, une copie de secours conserve l’ensemble des onglets
si au moins l’un d’eux est modifié. Après une interruption, la restauration
rouvre les documents comme des projets à enregistrer sous le nom de votre choix.
Cette copie peut perdre les 30 dernières secondes et ne remplace pas Ctrl+S.
Une seule instance de l’application est autorisée.

## Limites restantes

Pas encore de PSD, RAW, CMJN, gestion ICC, tampon, correcteur, baguette magique,
sélection automatique de sujet, courbes/niveaux, filtres dynamiques, groupes de
calques, effets de calque, objets dynamiques ou pinceaux avancés.
Les masques sont raster ; les formes sont rasterisées. Les transformations
rééchantillonnent les pixels, les réglages sont destructifs mais annulables.
Utilisez Atelier pour les créations écran, pas pour une chaîne d’impression
professionnelle. Les performances dépendent de la taille des images et du PC.

Limites par projet : 8192 px par côté, 16 millions de pixels de document,
100 calques et 256 Mo de pixels cumulés (masques inclus).

## Développement et validation

Python 3.12, PySide6 et Pillow. `Lancer-Atelier.cmd` installe les dépendances
la première fois puis ouvre le logiciel. `Construire-Windows.cmd` construit
une version portable ; Inno Setup 6 permet aussi de fabriquer l’installateur.

```sh
python -m pip install -r requirements.txt
python main.py
python -m unittest discover -s tests -v
```

13 tests passent sous Linux avec Qt : composition/opacité, gomme et sélection,
sauvegardes et recadrage, réglages avec alpha, PNG, gestes de dessin, masque
non destructif et sauvegarde, lasso, transformation avec annulation, texte
modifiable, verrouillage, onglets, extraction et récupération multi-documents.
La compilation GitHub exécute ces tests sous Windows et vérifie le démarrage
réel de la version empaquetée avant de produire l’installateur.
