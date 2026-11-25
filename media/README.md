# Dossier media/

Dépose ici les images et vidéos que l'agent peut envoyer sur la Page.
Seuls les fichiers de CE dossier sont accessibles à l'agent (par leur nom).

- Images : .jpg .jpeg .png .gif .bmp (10 Mo maximum)
- Vidéos : .mp4 .mov (200 Mo maximum)
- Les limites de taille sont un choix de prudence du projet, pas des limites Meta confirmées.
- Les fichiers de médias ne sont pas suivis par git (voir .gitignore), sauf `exemple.png`, utilisé par les tests `adk eval`.
- Dans `adk web`, un fichier joint avec le bouton de pièce jointe est copié ici automatiquement
  (plugin `fb_page_agent/media_upload_plugin.py`), avec un nom nettoyé (sans accents ni espaces).
  Un fichier du même nom n'est jamais écrasé : le nouveau reçoit un suffixe -2, -3...
