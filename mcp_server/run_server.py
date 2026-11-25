"""Lanceur stdio du serveur MCP Facebook (le server.py d'origine n'a pas de bloc de démarrage).

Ajouté par nous ; le server.py de HagaiHen reste intact. On y enregistre aussi
l'outil `save_draft_post` (brouillon non publié), qui n'existe pas dans l'original.
"""
from pathlib import Path
from typing import Any

from config import PAGE_ID
from manager import check_message
from server import mcp, manager


@mcp.tool()
def save_draft_post(message: str) -> dict[str, Any]:
    """Create an UNPUBLISHED draft post on the Page (visible only to Page admins).
    Input: message (str) - plain text, no [placeholders], no Markdown.
    Output: dict with the draft post ID, or an error.
    """
    return manager.save_draft_post(message)


@mcp.tool()
def list_page_comments(max_posts: int = 25) -> dict[str, Any]:
    """List the comments of ALL recent posts of the Page in one call (read-only).
    Input: max_posts (int, default 25) - how many recent posts to scan.
    Output: dict with posts_scanned, total_comments and a list of comments, each with
    post_id, post_label, comment_id, message, created_time and reply_count.
    reply_count = 0 means the comment has no reply at all (unanswered).
    When reply_count > 0, page_replied tells whether the PAGE itself replied
    (True/False; None = unknown). replies_unknown_author counts replies whose author
    Facebook does not disclose: they may be customers, so page_replied=False with
    replies_unknown_author > 0 does NOT mean the Page answered.
    """
    posts = manager.get_page_posts().get("data", [])[: max(1, min(max_posts, 100))]
    comments: list[dict[str, Any]] = []
    for p in posts:
        resp = manager.api._request(
            "GET", f"{p['id']}/comments",
            {"fields": "id,message,created_time,comment_count", "limit": 100},
        )
        if "error" in resp:
            return {"error": resp["error"], "posts_scanned": len(comments)}
        label = (p.get("message") or p.get("story") or "")[:60]
        for c in resp.get("data", []):
            entry = {
                "post_id": p["id"], "post_label": label,
                "comment_id": c["id"], "message": c.get("message", ""),
                "created_time": c.get("created_time"),
                "reply_count": c.get("comment_count", 0),
            }
            if entry["reply_count"] > 0:
                # Qui a répondu ? Facebook donne `from` pour les réponses de la Page ;
                # quand il manque, l'auteur est inconnu (jamais présumé « client »).
                rep = manager.api._request(
                    "GET", f"{c['id']}/comments", {"fields": "id,from", "limit": 100})
                replies = rep.get("data", []) if "error" not in rep else None
                if replies is None:
                    entry["page_replied"] = None  # inconnu : la lecture des réponses a échoué
                else:
                    entry["page_replied"] = any(
                        (r.get("from") or {}).get("id") == PAGE_ID for r in replies)
                    entry["replies_unknown_author"] = sum(1 for r in replies if not r.get("from"))
            comments.append(entry)
    return {"posts_scanned": len(posts), "total_comments": len(comments), "comments": comments}


PAGE_METRICS = [
    "page_media_view",              # vues du contenu (remplace page_impressions)
    "page_total_media_view_unique", # personnes distinctes ayant vu le contenu
    "page_views_total",             # visites du profil de la Page
    "page_post_engagements",        # interactions sur les posts
    "page_daily_follows_unique",    # nouveaux abonnés
    "page_daily_unfollows_unique",  # désabonnements
    "page_follows",                 # total d'abonnés (valeur du dernier jour)
]


@mcp.tool()
def get_page_insights(days: int = 28) -> dict[str, Any]:
    """Page-level statistics over the last N days (read-only).
    Input: days (int, default 28, max 90).
    Output: dict with period, and per metric the total over the period (and the
    daily values). page_follows is a snapshot: use its last value, not the sum.
    page_total_media_view_unique is unique PER DAY: its sum counts the same person
    several times, so never present it as a number of distinct people.
    An all-zero metric means no activity (not an access problem) unless `error` is set.
    """
    import time
    days = max(1, min(days, 90))
    until = int(time.time())
    since = until - days * 86400
    from datetime import datetime, timezone
    result: dict[str, Any] = {
        "days": days,
        "since": datetime.fromtimestamp(since, timezone.utc).strftime("%Y-%m-%d"),
        "until": datetime.fromtimestamp(until, timezone.utc).strftime("%Y-%m-%d"),
        "metrics": {},
    }
    for m in PAGE_METRICS:
        resp = manager.api._request(
            "GET", f"{PAGE_ID}/insights",
            {"metric": m, "period": "day", "since": since, "until": until},
        )
        if "error" in resp:
            result["metrics"][m] = {"error": resp["error"].get("message", "unknown")}
            continue
        points = [
            (v.get("end_time", "")[:10], v.get("value", 0))
            for d in resp.get("data", []) for v in d.get("values", [])
            if isinstance(v.get("value", 0), (int, float))
        ]
        entry: dict[str, Any] = {
            "last_value": points[-1][1] if points else None,
            "last_date": points[-1][0] if points else None,
            "total": None if m == "page_follows" else sum(p[1] for p in points),
            "daily": [{"date": d, "value": x} for d, x in points],
        }
        if points and m != "page_follows":
            best = max(points, key=lambda p: p[1])
            entry["max_value"], entry["max_date"] = best[1], best[0]
        result["metrics"][m] = entry
    return result


# --- Médias : envoi de fichiers locaux, limité au dossier media/ -------------------
# Un chemin libre permettrait d'envoyer n'importe quel fichier du PC sur Facebook :
# on n'accepte donc qu'un NOM de fichier présent directement dans media/.
MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024    # limites choisies par prudence, non tirées de la doc Meta
MAX_VIDEO_BYTES = 200 * 1024 * 1024


def _media_file(filename: str, extensions: set[str], max_bytes: int) -> tuple[Path | None, str | None]:
    """Valide un nom de fichier du dossier media/. Retourne (chemin, None) ou (None, erreur)."""
    if not filename or filename != Path(filename).name or filename.startswith("."):
        return None, "Donne uniquement un nom de fichier du dossier media/, sans chemin."
    path = MEDIA_DIR / filename
    if path.is_symlink() or not path.is_file():
        return None, f"Fichier introuvable dans media/ : {filename}"
    if path.resolve().parent != MEDIA_DIR.resolve():
        return None, "Fichier hors du dossier media/."
    if path.suffix.lower() not in extensions:
        return None, f"Extension refusée ({path.suffix}). Autorisées : {', '.join(sorted(extensions))}"
    size = path.stat().st_size
    if size == 0 or size > max_bytes:
        return None, f"Taille refusée : {size} octets (maximum {max_bytes})."
    return path, None


def _upload(endpoint: str, path: Path, data: dict[str, Any], timeout: int) -> dict[str, Any]:
    import requests
    from config import GRAPH_API_BASE_URL, PAGE_ACCESS_TOKEN
    with path.open("rb") as fh:
        resp = requests.post(
            f"{GRAPH_API_BASE_URL}/{PAGE_ID}/{endpoint}",
            data={**data, "access_token": PAGE_ACCESS_TOKEN},
            files={"source": (path.name, fh)},
            timeout=timeout,
        )
    try:
        return resp.json()
    except ValueError:
        return {"error": {"message": f"Réponse non JSON (HTTP {resp.status_code})"}}


@mcp.tool()
def list_media_files() -> dict[str, Any]:
    """List the image and video files available in the media/ folder (read-only).
    Output: images and videos, each with name and size in bytes. Only these files can be posted.
    """
    out: dict[str, list[dict[str, Any]]] = {"images": [], "videos": []}
    if MEDIA_DIR.is_dir():
        for p in sorted(MEDIA_DIR.iterdir()):
            if not p.is_file() or p.name.startswith("."):
                continue
            item = {"name": p.name, "bytes": p.stat().st_size}
            if p.suffix.lower() in IMAGE_EXTENSIONS:
                out["images"].append(item)
            elif p.suffix.lower() in VIDEO_EXTENSIONS:
                out["videos"].append(item)
    return out


def _schedule_fields(published: bool, scheduled_time: int) -> tuple[dict[str, Any] | None, str | None]:
    """Champs de publication : publiée, non publiée, ou planifiée (heure Unix)."""
    import time
    if not scheduled_time:
        return {"published": str(published).lower()}, None
    delay = scheduled_time - time.time()
    if delay < 10 * 60:
        return None, "Facebook exige au moins 10 minutes d'avance (utilise get_current_time, +11 minutes)."
    if delay > 30 * 24 * 3600:
        return None, "Planification limitée à environ 30 jours (limite non vérifiée sur la doc Meta)."
    return {"published": "false", "scheduled_publish_time": str(int(scheduled_time))}, None


@mcp.tool()
def post_image_file(filename: str, caption: str, published: bool = False, scheduled_time: int = 0) -> dict[str, Any]:
    """Upload an image from the media/ folder to the Page with a caption.
    Input: filename (name only, from list_media_files), caption (final plain text, no
    [placeholders], no Markdown), published (False = unpublished, visible to admins only;
    True = public immediately), scheduled_time (Unix timestamp, optional: schedule the
    publication instead; at least 10 minutes ahead, see get_current_time/to_unix_timestamp).
    Use published=True only if the user asked to publish.
    """
    if (err := check_message(caption)):
        return {"error": {"message": err, "code": "TEXTE_INVALIDE"}}
    path, err = _media_file(filename, IMAGE_EXTENSIONS, MAX_IMAGE_BYTES)
    if err:
        return {"error": {"message": err, "code": "FICHIER_INVALIDE"}}
    fields, err = _schedule_fields(published, scheduled_time)
    if err:
        return {"error": {"message": err, "code": "HEURE_INVALIDE"}}
    return _upload("photos", path, {"caption": caption, **fields}, timeout=120)


@mcp.tool()
def post_video_file(filename: str, description: str, published: bool = False, scheduled_time: int = 0) -> dict[str, Any]:
    """Upload a video from the media/ folder to the Page with a description.
    Input: filename (name only, from list_media_files), description (final plain text, no
    [placeholders], no Markdown), published (False = unpublished, True = public immediately),
    scheduled_time (Unix timestamp, optional: schedule the publication; at least 10 minutes ahead).
    Use published=True only if the user asked to publish. Facebook processes videos
    after the upload: the post may take a few minutes to appear.
    """
    if (err := check_message(description)):
        return {"error": {"message": err, "code": "TEXTE_INVALIDE"}}
    path, err = _media_file(filename, VIDEO_EXTENSIONS, MAX_VIDEO_BYTES)
    if err:
        return {"error": {"message": err, "code": "FICHIER_INVALIDE"}}
    fields, err = _schedule_fields(published, scheduled_time)
    if err:
        return {"error": {"message": err, "code": "HEURE_INVALIDE"}}
    return _upload("videos", path, {"description": description, **fields}, timeout=570)


@mcp.tool()
def post_photos_files(filenames: list[str], caption: str, published: bool = False, scheduled_time: int = 0) -> dict[str, Any]:
    """Create ONE post with several photos from the media/ folder (2 to 10 images).
    Input: filenames (names only, from list_media_files), caption (final plain text),
    published (False = unpublished), scheduled_time (Unix timestamp, optional).
    Use published=True only if the user asked to publish.
    """
    import json as _json
    if not 2 <= len(filenames) <= 10:
        return {"error": {"message": "Donne entre 2 et 10 images (pour une seule image, utilise post_image_file).", "code": "NOMBRE_INVALIDE"}}
    if len(set(filenames)) != len(filenames):
        return {"error": {"message": "Même fichier donné plusieurs fois.", "code": "FICHIER_INVALIDE"}}
    if (err := check_message(caption)):
        return {"error": {"message": err, "code": "TEXTE_INVALIDE"}}
    paths = []
    for name in filenames:  # tout valider AVANT d'envoyer quoi que ce soit
        path, err = _media_file(name, IMAGE_EXTENSIONS, MAX_IMAGE_BYTES)
        if err:
            return {"error": {"message": f"{name} : {err}", "code": "FICHIER_INVALIDE"}}
        paths.append(path)
    fields, err = _schedule_fields(published, scheduled_time)
    if err:
        return {"error": {"message": err, "code": "HEURE_INVALIDE"}}
    media_ids = []
    for path in paths:  # photos temporaires, non publiées, rattachées ensuite au post
        r = _upload("photos", path, {"published": "false", "temporary": "true"}, timeout=120)
        if "id" not in r:
            return {"error": {"message": f"Envoi de {path.name} échoué, aucun post créé.", "details": r.get("error")}}
        media_ids.append(r["id"])
    data: dict[str, Any] = {"message": caption, **fields}
    for i, mid in enumerate(media_ids):
        data[f"attached_media[{i}]"] = _json.dumps({"media_fbid": mid})
    return manager.api._request("POST", f"{PAGE_ID}/feed", data)


@mcp.tool()
def post_link(link: str, message: str, published: bool = False, scheduled_time: int = 0) -> dict[str, Any]:
    """Create a post that shares a web link, with a text (catalogue page, article...).
    Input: link (http/https URL given by the user), message (final plain text),
    published (False = unpublished), scheduled_time (Unix timestamp, optional).
    Use published=True only if the user asked to publish. Never invent a URL.
    """
    from urllib.parse import urlparse
    if urlparse(link).scheme not in ("http", "https") or not urlparse(link).netloc:
        return {"error": {"message": "Lien invalide : une URL http(s) complète est attendue.", "code": "LIEN_INVALIDE"}}
    if (err := check_message(message)):
        return {"error": {"message": err, "code": "TEXTE_INVALIDE"}}
    fields, err = _schedule_fields(published, scheduled_time)
    if err:
        return {"error": {"message": err, "code": "HEURE_INVALIDE"}}
    return manager.api._request("POST", f"{PAGE_ID}/feed", {"message": message, "link": link, **fields})


@mcp.tool()
def comment_on_post(post_id: str, message: str) -> dict[str, Any]:
    """Post a top-level comment on a post, as the Page (not a reply to a comment).
    Input: post_id (full post ID), message (final plain text, no [placeholders], no Markdown).
    """
    if (err := check_message(message)):
        return {"error": {"message": err, "code": "TEXTE_INVALIDE"}}
    return manager.api._request("POST", f"{post_id}/comments", {"message": message})


@mcp.tool()
def list_conversations(limit: int = 10) -> dict[str, Any]:
    """List the Page's Messenger conversations, most recent first (read-only, private data).
    Output: for each conversation: id, updated_time, message_count, snippet (last message
    start) and participant names.
    """
    resp = manager.api._request("GET", f"{PAGE_ID}/conversations", {
        "fields": "id,updated_time,message_count,snippet,participants",
        "limit": max(1, min(limit, 25))})
    if "error" in resp:
        return {"error": resp["error"]}
    return {"conversations": [
        {"id": c["id"], "updated_time": c.get("updated_time"), "message_count": c.get("message_count"),
         "snippet": c.get("snippet", ""),
         "participants": [p.get("name") for p in c.get("participants", {}).get("data", [])]}
        for c in resp.get("data", [])]}


@mcp.tool()
def get_conversation_messages(conversation_id: str, limit: int = 10) -> dict[str, Any]:
    """Read the latest messages of one Messenger conversation (read-only, private data).
    Input: conversation_id (from list_conversations), limit (default 10, max 25).
    Output: messages with created_time, sender name and text, newest first. Does not send anything.
    """
    resp = manager.api._request("GET", f"{conversation_id}/messages", {
        "fields": "id,created_time,message,from", "limit": max(1, min(limit, 25))})
    if "error" in resp:
        return {"error": resp["error"]}
    return {"messages": [
        {"created_time": m.get("created_time"), "from": (m.get("from") or {}).get("name"),
         "from_page": (m.get("from") or {}).get("id") == PAGE_ID, "text": m.get("message", "")}
        for m in resp.get("data", [])]}


MADAGASCAR_UTC_OFFSET_HOURS = 3  # Madagascar : UTC+3, pas d'heure d'été


@mcp.tool()
def get_current_time() -> dict[str, Any]:
    """Current date and time (read-only). Use it before scheduling a post.
    Output: unix_timestamp, utc, and local time in Madagascar (UTC+3).
    """
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    local = now.astimezone(timezone(timedelta(hours=MADAGASCAR_UTC_OFFSET_HOURS)))
    return {
        "unix_timestamp": int(now.timestamp()),
        "utc": now.strftime("%Y-%m-%d %H:%M:%S"),
        "madagascar_time": local.strftime("%Y-%m-%d %H:%M:%S"),
        "madagascar_utc_offset": "+03:00",
    }


@mcp.tool()
def to_unix_timestamp(date: str, time: str, utc_offset_hours: int = MADAGASCAR_UTC_OFFSET_HOURS) -> dict[str, Any]:
    """Convert a local date and time to a Unix timestamp for schedule_post (read-only).
    Input: date 'YYYY-MM-DD', time 'HH:MM' (24h), utc_offset_hours (default 3 = Madagascar).
    Output: unix_timestamp, and minutes_from_now (Facebook needs at least 10 minutes
    and at most about 30 days ahead; use at least 11 to be safe).
    """
    from datetime import datetime, timedelta, timezone
    try:
        local = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").replace(
            tzinfo=timezone(timedelta(hours=utc_offset_hours)))
    except ValueError:
        return {"error": "Format attendu : date YYYY-MM-DD, time HH:MM"}
    ts = int(local.timestamp())
    return {"unix_timestamp": ts, "local": f"{date} {time} (UTC{utc_offset_hours:+d})",
            "minutes_from_now": round((ts - datetime.now(timezone.utc).timestamp()) / 60, 1)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
