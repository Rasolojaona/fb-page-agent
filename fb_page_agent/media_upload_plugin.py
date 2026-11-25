"""Plugin ADK : enregistre dans media/ les images et vidéos jointes à un message.

Dans `adk web`, le bouton de pièce jointe envoie le fichier au modèle. Nos outils
(post_image_file, post_video_file) ne lisent que le dossier media/ : ce plugin y copie
le fichier joint, après contrôle, et remplace la pièce jointe par un message texte
donnant le nom du fichier enregistré. Le modèle ne reçoit donc jamais les octets.

Les règles (extensions, tailles) reproduisent celles de mcp_server/run_server.py.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 200 * 1024 * 1024
_MIME_EXTENSIONS = {
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/bmp": ".bmp",
    "video/mp4": ".mp4", "video/quicktime": ".mov",
}


def clean_filename(name: str) -> str:
    """Nom simple et sûr : sans chemin, sans accents, sans espaces ni symboles."""
    name = Path(name.replace("\\", "/")).name
    stem, suffix = Path(name).stem, Path(name).suffix.lower()
    ascii_stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    ascii_stem = re.sub(r"[^A-Za-z0-9_-]+", "-", ascii_stem).strip("-_") or "fichier"
    return ascii_stem[:80] + suffix


def _free_name(name: str) -> str:
    """Ne jamais écraser un fichier existant : ajoute -2, -3, ..."""
    candidate, stem, suffix, i = name, Path(name).stem, Path(name).suffix, 2
    while (MEDIA_DIR / candidate).exists():
        candidate = f"{stem}-{i}{suffix}"
        i += 1
    return candidate


class MediaUploadPlugin(BasePlugin):
    def __init__(self, name: str = "media_upload_plugin"):
        super().__init__(name)

    async def on_user_message_callback(
        self, *, invocation_context: InvocationContext, user_message: types.Content
    ) -> Optional[types.Content]:
        if not user_message.parts or not any(p.inline_data for p in user_message.parts):
            return None
        new_parts: list[types.Part] = []
        for i, part in enumerate(user_message.parts):
            blob = part.inline_data
            if blob is None:
                new_parts.append(part)
                continue
            new_parts.append(types.Part(text=self._save(blob, invocation_context.invocation_id, i)))
        return types.Content(role=user_message.role or "user", parts=new_parts)

    def _save(self, blob: types.Blob, invocation_id: str, index: int) -> str:
        data = blob.data or b""
        original = blob.display_name or f"upload-{invocation_id[:8]}-{index}"
        name = clean_filename(original)
        suffix = Path(name).suffix.lower()
        if not suffix:  # pas d'extension : on la déduit du type MIME
            suffix = _MIME_EXTENSIONS.get((blob.mime_type or "").lower(), "")
            name += suffix
        if suffix in IMAGE_EXTENSIONS:
            kind, limit = "image", MAX_IMAGE_BYTES
        elif suffix in VIDEO_EXTENSIONS:
            kind, limit = "vidéo", MAX_VIDEO_BYTES
        else:
            return (f"Fichier refusé (type non pris en charge : {suffix or blob.mime_type or 'inconnu'}) : "
                    f"{original}. Seuls les images et vidéos sont acceptées.")
        if not data or len(data) > limit:
            return f"Fichier refusé (taille {len(data)} octets, maximum {limit}) : {original}."
        MEDIA_DIR.mkdir(exist_ok=True)
        final = _free_name(name)
        (MEDIA_DIR / final).write_bytes(data)
        return (f"Fichier reçu et enregistré dans media/ : {final} ({kind}, "
                f"{len(data) / (1024 * 1024):.1f} Mo). Utilise exactement ce nom de fichier.")
