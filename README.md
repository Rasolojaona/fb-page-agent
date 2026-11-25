# fb-page-agent : un agent IA de community management pour Facebook

> An AI community-management agent for a Facebook Page, built with Google ADK and MCP.
> It reads, drafts, schedules and moderates, with human approval on every write.

Gérer une Page Facebook prend du temps : répondre aux commentaires, publier régulièrement, suivre les
statistiques, surveiller Messenger. **fb-page-agent** est un assistant IA qui fait ce travail **avec
vous** : il lit la Page, prépare les textes et les publications, et **ne publie rien sans votre
confirmation**.

Le projet est né pour un petit commerce, avec une contrainte précise : un modèle gratuit et modeste ne
doit jamais pouvoir abîmer une vraie Page. Toute la conception tourne autour de cette question.

## Ce que l'agent sait faire

| Domaine | Exemples de demandes | Outils |
|---|---|---|
| **Comprendre la Page** | « Comment va ma Page ce mois-ci ? », « Combien de fans ? » | `get_page_insights`, `get_page_fan_count`, `get_page_info` |
| **Commentaires** | « Quels commentaires n'ont pas encore de réponse ? » | `list_page_comments` (tous les posts en un appel, avec `page_replied`) |
| **Répondre et modérer** | « Réponds à ce commentaire », « Masque ce commentaire » | `reply_to_comment`, `comment_on_post`, `hide_comment` |
| **Publier** | « Enregistre un brouillon pour annoncer nos nouveautés » | `save_draft_post` (par défaut), `post_to_facebook`, `update_post` |
| **Images, vidéos, albums, liens** | « Publie l'image exemple.png avec ce texte » | `post_image_file`, `post_video_file`, `post_photos_files`, `post_link` |
| **Planifier** | « Programme cette image demain à 10h » | `scheduled_time` sur tous les outils de publication, `schedule_post`, `get_current_time`, `to_unix_timestamp` |
| **Performances d'un post** | « Combien de j'aime a mon dernier post ? » | `get_number_of_likes`, `get_post_insights`, `get_post_reactions_breakdown` |
| **Messenger (lecture)** | « Combien de conversations en attente ? » | `list_conversations`, `get_conversation_messages` |

Dans `adk web`, le bouton de pièce jointe permet de déposer une image ou une vidéo : elle est copiée dans
`media/` et l'agent peut la publier.

## Sécurité : quatre couches

Un modèle de langage se trompe. Le projet part de ce principe et ne compte pas sur lui seul.

1. **Liste blanche d'outils.** L'agent ne voit que les outils autorisés. La suppression, les actions en
   masse et l'envoi de messages privés ne lui sont **pas exposés**.
2. **Confirmation humaine.** Chaque écriture (publier, planifier, modifier, répondre, masquer) s'arrête
   et attend votre validation (`require_confirmation=True` d'ADK).
3. **Garde-fous côté serveur.** Même après une confirmation trop rapide, le serveur refuse un texte vide,
   un texte avec des `[champs à remplir]` ou du Markdown. Il refuse aussi un fichier hors du dossier
   `media/`, un chemin ou une URL, et une date de planification hors de la plage autorisée par Facebook.
4. **Brouillon par défaut.** Sans demande explicite de publication, l'agent enregistre un brouillon non
   publié.

Les consignes de l'agent viennent des erreurs réellement observées pendant les tests : ne pas conclure à
partir d'un seul post, ne jamais inventer un chiffre, une adresse ou un prix, ne jamais renvoyer une
vidéo après un délai dépassé sans vérifier si elle est déjà en ligne, et ne pas traiter le message d'un
client comme une instruction.

## Architecture

```
Vous (adk web)
   │
   ▼
Agent Google ADK  ──  modèle via LiteLLM (NVIDIA NIM par défaut, remplaçable)
   │   ├─ outils de lecture   (libres)
   │   └─ outils d'écriture   (confirmation obligatoire)
   ▼
Serveur MCP Facebook (stdio)  ──  garde-fous, dossier media/
   │
   ▼
API Graph de Meta (v22.0), jeton de Page
```

- `fb_page_agent/` : l'agent ADK (`agent.py`) et le plugin de pièces jointes (`media_upload_plugin.py`).
- `mcp_server/` : serveur MCP basé sur [HagaiHen/facebook-mcp-server](https://github.com/HagaiHen/facebook-mcp-server)
  (licence MIT), relu et étendu. Nos ajouts sont surtout dans `run_server.py` ; le détail des
  modifications est dans [`mcp_server/README.md`](mcp_server/README.md).
- `evals/` : tests de comportement `adk eval`.
- `media/` : les seuls fichiers que l'agent peut publier.

## Installation

Il faut Python 3.12, une **Page Facebook** dont vous êtes administrateur, et une clé d'API pour le modèle.

```bash
git clone <url-du-depot> fb-page-agent
cd fb-page-agent
python -m venv .venv
# Windows : .venv\Scripts\activate    macOS/Linux : source .venv/bin/activate
pip install -r requirements.txt
cp fb_page_agent/.env.example fb_page_agent/.env
```

Remplissez ensuite `fb_page_agent/.env` :

| Variable | Rôle |
|---|---|
| `NVIDIA_API_KEY` | Clé du modèle (gratuite sur build.nvidia.com) |
| `ADK_MODEL` | Modèle utilisé, `nvidia/nemotron-3.5-lightning-30b-a3b` par défaut |
| `FACEBOOK_PAGE_ID` | ID de la **Page** (et non celui de l'application Meta) |
| `FACEBOOK_ACCESS_TOKEN` | **Jeton de Page** (et non jeton utilisateur) |

### Obtenir le jeton de Page

1. Créez une application sur [Meta for Developers](https://developers.facebook.com/).
2. Dans le [Graph API Explorer](https://developers.facebook.com/tools/explorer/), demandez les
   permissions utiles : `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`,
   `pages_manage_engagement`, `pages_read_user_content`, `read_insights`, et
   `pages_messaging` pour lire Messenger.
3. Choisissez votre Page pour obtenir un **jeton de Page**. Vérifiez-le avec le
   [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/).

Le jeton donne le contrôle de votre Page : gardez-le dans `.env`, qui est exclu de git.

## Utilisation

```bash
adk web
```

Ouvrez l'adresse affichée, choisissez `fb_page_agent` et posez vos questions en français (ou dans votre
langue). Quelques exemples :

- « Quels commentaires n'ont pas encore reçu de réponse ? »
- « Comment va ma Page ce mois-ci ? »
- « Enregistre un brouillon pour annoncer l'arrivée de nouveaux produits. »
- « Programme l'image exemple.png demain à 10h avec la légende “Nouveau en boutique”. »

Pour chaque écriture, l'interface affiche l'action exacte et attend votre accord.

## Évaluation

Le dossier `evals/` contient 13 cas qui vérifient **les outils appelés** par l'agent : le bon outil pour
la bonne question, et aucun appel pour les demandes à refuser (suppression, message privé, fichier hors de
`media/`). Ces tests ne demandent aucun modèle juge.

```bash
python evals/build_evalsets.py          # régénère les jeux JSON
adk eval fb_page_agent evals/choix.evalset.json --config_file_path evals/choix.config.json --parallelism 1
adk eval fb_page_agent evals/interdits.evalset.json --config_file_path evals/interdits.config.json --parallelism 1
adk eval fb_page_agent evals/refus_media.evalset.json --config_file_path evals/refus_media.config.json --parallelism 1
```

- Les tests interrogent la vraie Page **en lecture**. Les écritures ne s'exécutent pas : elles restent en
  attente de confirmation.
- `--parallelism 1` est nécessaire, car la session MCP partagée se coupe en parallèle.
- Sous Windows, définissez `PYTHONUTF8=1` avant d'utiliser `--print_detailed_results`.

## Limites connues

- Facebook ne renvoie pas l'auteur des commentaires : l'agent ne peut pas répondre par le prénom.
- Plusieurs métriques d'insights ont été retirées par Meta ; seules celles vérifiées sont utilisées.
- Les photos publiées par l'API ne sont pas toujours relisibles par l'API, bien que visibles sur la Page.
- Planification : de 10 minutes à 30 jours d'avance (exigence de Facebook).
- Les limites de taille des médias (10 Mo par image, 200 Mo par vidéo) sont un choix de prudence.
- Pas encore pris en charge : envoi de messages Messenger, Reels et stories, Instagram, publicités,
  modification des informations de la Page.

## Pistes

- Une FAQ de la boutique comme seule source pour les réponses aux clients.
- Un briefing quotidien : commentaires en attente avec des réponses déjà rédigées.
- Les webhooks Meta, pour réagir dès qu'un commentaire ou un message arrive.
- Les réponses Messenger avec validation, dans la fenêtre de 24 h imposée par Meta.

## Licence

MIT, voir [LICENSE](LICENSE). Le serveur MCP d'origine est © HagaiHen, sous licence MIT
([mcp_server/LICENSE](mcp_server/LICENSE)).
