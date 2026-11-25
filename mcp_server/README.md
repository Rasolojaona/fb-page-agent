# Serveur MCP Facebook (copie relue)

Source : https://github.com/HagaiHen/facebook-mcp-server (licence MIT)
Commit copié : `61b2128555d7582b19daf772186c03bc051c1c05` (2026-04-23)

Fichiers d'origine non modifiés : `server.py`, `config.py`, `requirements.txt`, `LICENSE`.
Ajouté par nous : `run_server.py` (le `server.py` n'a pas de bloc de démarrage).

## Modifications locales (2026-11-17) par rapport au commit d'origine
- `facebook_api.py` : `get_posts` demande aussi `story`, `status_type`, `permalink_url` (les événements automatiques n'ont pas de `message`) ; `timeout=30` sur les requêtes ; suppression des liens `paging.previous/next` qui contiennent le jeton en clair.
- `manager.py` : `get_post_insights` sans les métriques retirées par Meta (`post_impressions`, `_paid`, `_organic`, `post_engaged_users`) ; `get_post_reactions_breakdown` renvoie des zéros explicites au lieu de `{}` et propage les erreurs.
- `manager.py` : garde-fou `check_message()` sur `post_to_facebook`, `schedule_post`, `update_post` et `save_draft_post` (refuse texte vide, `[placeholders]`, Markdown) ; nouvelle méthode `save_draft_post` (post non publié).
- `run_server.py` : enregistre les outils MCP `save_draft_post` et `list_page_comments` (commentaires de tous les posts récents en un appel, avec `reply_count`).
- `run_server.py` : nouvel outil `get_page_insights(days)` (statistiques de la Page : vues, visites, interactions, abonnés/désabonnés). Métriques vérifiées le 2026-11-18 ; `page_impressions`, `page_fans`, `page_fan_adds`, `page_engaged_users`, `page_consumptions` sont refusées par Meta.
- `run_server.py` : `get_current_time` et `to_unix_timestamp` (heure de Madagascar, UTC+3) pour planifier ; `list_page_comments` renvoie `page_replied` et `replies_unknown_author`.
- `run_server.py` : médias (`list_media_files`, `post_image_file`, `post_video_file`, `post_photos_files`, limités au dossier `media/`), `post_link`, `comment_on_post`, planification par `scheduled_time` (10 min à 30 jours), lecture Messenger (`list_conversations`, `get_conversation_messages`). Tous passent par le garde-fou `check_message`.
- `manager.py` : `post_image_to_facebook` (URL) reçoit le même garde-fou.
- `facebook_api.py` : `get_page_fan_count` lève une erreur si l'API échoue (au lieu de renvoyer `0`).

Relecture (2026-11-17) : `facebook_api.py` et `manager.py` n'appellent que `graph.facebook.com` avec le jeton de Page ; pas d'exécution de commande ni d'écriture de fichier.
Point faible restant : le jeton est passé en paramètre d'URL (comportement d'origine du serveur).

Compatibilité : nécessite `mcp<2` (mcp 2.x a renommé FastMCP).
