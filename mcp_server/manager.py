import re
from typing import Any
from facebook_api import FacebookAPI


def check_message(message: str) -> str | None:
    """Garde-fou (ajout local) : refuse un texte qui n'est pas publiable tel quel.

    Retourne un message d'erreur, ou None si le texte est correct.
    """
    if not message or not message.strip():
        return "Texte vide."
    if re.search(r"\[[^\]\n]{1,80}\]", message):
        return ("Le texte contient un champ à remplir entre crochets (ex. [adresse]). "
                "Remplace-le par la vraie information (voir get_page_info) avant d'écrire.")
    if "**" in message or re.search(r"^\s*#{1,6}\s", message, re.M):
        return "Facebook n'affiche pas le Markdown (** ou #) : écris du texte brut."
    return None


class Manager:
    def __init__(self):
        self.api = FacebookAPI()

    def save_draft_post(self, message: str) -> dict[str, Any]:
        """Crée un brouillon NON publié (visible seulement des admins de la Page)."""
        if (err := check_message(message)):
            return {"error": {"message": err, "code": "TEXTE_INVALIDE"}}
        return self.api._request("POST", f"{__import__('config').PAGE_ID}/feed",
                                 {"message": message, "published": False})

    def post_to_facebook(self, message: str) -> dict[str, Any]:
        if (err := check_message(message)):
            return {"error": {"message": err, "code": "TEXTE_INVALIDE"}}
        return self.api.post_message(message)

    def reply_to_comment(self, post_id: str, comment_id: str, message: str) -> dict[str, Any]:
        return self.api.reply_to_comment(comment_id, message)

    def get_page_posts(self) -> dict[str, Any]:
        return self.api.get_posts()

    def get_post_comments(self, post_id: str) -> dict[str, Any]:
        return self.api.get_comments(post_id)

    def delete_post(self, post_id: str) -> dict[str, Any]:
        return self.api.delete_post(post_id)

    def delete_comment(self, comment_id: str) -> dict[str, Any]:
        return self.api.delete_comment(comment_id)

    def hide_comment(self, comment_id: str) -> dict[str, Any]:
        return self.api.hide_comment(comment_id)

    def unhide_comment(self, comment_id: str) -> dict[str, Any]:
        return self.api.unhide_comment(comment_id)

    def delete_comment_from_post(self, post_id: str, comment_id: str) -> dict[str, Any]:
        return self.api.delete_comment(comment_id)

    def filter_negative_comments(self, comments: dict[str, Any]) -> list[dict[str, Any]]:
        keywords = ["bad", "terrible", "awful", "hate", "dislike", "problem", "issue"]
        return [c for c in comments.get("data", []) if any(k in c.get("message", "").lower() for k in keywords)]

    def get_number_of_comments(self, post_id: str) -> int:
        return len(self.api.get_comments(post_id).get("data", []))

    def get_number_of_likes(self, post_id: str) -> int:
        return self.api._request("GET", post_id, {"fields": "likes.summary(true)"}).get("likes", {}).get("summary", {}).get("total_count", 0)

    def get_post_insights(self, post_id: str) -> dict[str, Any]:
        # post_impressions, _paid, _organic et post_engaged_users retirés : Meta les refuse
        # (erreur #100 "must be a valid insights metric"), ce qui faisait échouer tout l'appel.
        metrics = [
            "post_impressions_unique", "post_clicks",
            "post_reactions_like_total", "post_reactions_love_total", "post_reactions_wow_total",
            "post_reactions_haha_total", "post_reactions_sorry_total", "post_reactions_anger_total",
        ]
        return self.api.get_bulk_insights(post_id, metrics)
    
    def get_post_impressions(self, post_id: str) -> dict[str, Any]:
        return self.api.get_insights(post_id, "post_impressions")

    def get_post_impressions_unique(self, post_id: str) -> dict[str, Any]:
        return self.api.get_insights(post_id, "post_impressions_unique")

    def get_post_impressions_paid(self, post_id: str) -> dict[str, Any]:
        return self.api.get_insights(post_id, "post_impressions_paid")

    def get_post_impressions_organic(self, post_id: str) -> dict[str, Any]:
        return self.api.get_insights(post_id, "post_impressions_organic")

    def get_post_engaged_users(self, post_id: str) -> dict[str, Any]:
        return self.api.get_insights(post_id, "post_engaged_users")

    def get_post_clicks(self, post_id: str) -> dict[str, Any]:
        return self.api.get_insights(post_id, "post_clicks")

    def get_post_reactions_like_total(self, post_id: str) -> dict[str, Any]:
        return self.api.get_insights(post_id, "post_reactions_like_total")

    def get_post_reactions_love_total(self, post_id: str) -> dict[str, Any]:
        return self.api.get_insights(post_id, "post_reactions_love_total")

    def get_post_reactions_wow_total(self, post_id: str) -> dict[str, Any]:
        return self.api.get_insights(post_id, "post_reactions_wow_total")

    def get_post_reactions_haha_total(self, post_id: str) -> dict[str, Any]:
        return self.api.get_insights(post_id, "post_reactions_haha_total")

    def get_post_reactions_sorry_total(self, post_id: str) -> dict[str, Any]:
        return self.api.get_insights(post_id, "post_reactions_sorry_total")

    def get_post_reactions_anger_total(self, post_id: str) -> dict[str, Any]:
        return self.api.get_insights(post_id, "post_reactions_anger_total")

    def get_post_top_commenters(self, post_id: str) -> list[dict[str, Any]]:
        comments = self.get_post_comments(post_id).get("data", [])
        counter = {}
        for comment in comments:
            user_id = comment.get("from", {}).get("id")
            if user_id:
                counter[user_id] = counter.get(user_id, 0) + 1
        return sorted([{"user_id": k, "count": v} for k, v in counter.items()], key=lambda x: x["count"], reverse=True)

    def post_image_to_facebook(self, image_url: str, caption: str) -> dict[str, Any]:
        # Ajout local : même garde-fou que pour les posts texte (légende finale, sans Markdown).
        if (err := check_message(caption)):
            return {"error": {"message": err, "code": "TEXTE_INVALIDE"}}
        return self.api.post_image_to_facebook(image_url, caption)

    def send_dm_to_user(self, user_id: str, message: str) -> dict[str, Any]:
        return self.api.send_dm_to_user(user_id, message)
    
    def update_post(self, post_id: str, new_message: str) -> dict[str, Any]:
        if (err := check_message(new_message)):
            return {"error": {"message": err, "code": "TEXTE_INVALIDE"}}
        return self.api.update_post(post_id, new_message)

    def schedule_post(self, message: str, publish_time: int) -> dict[str, Any]:
        if (err := check_message(message)):
            return {"error": {"message": err, "code": "TEXTE_INVALIDE"}}
        return self.api.schedule_post(message, publish_time)

    def get_page_fan_count(self) -> int:
        return self.api.get_page_fan_count()

    def get_post_share_count(self, post_id: str) -> int:
        return self.api.get_post_share_count(post_id)

    def get_post_reactions_breakdown(self, post_id: str) -> dict[str, Any]:
        """Return counts for all reaction types on a post."""
        metrics = [
            "post_reactions_like_total",
            "post_reactions_love_total",
            "post_reactions_wow_total",
            "post_reactions_haha_total",
            "post_reactions_sorry_total",
            "post_reactions_anger_total",
        ]
        raw = self.api.get_bulk_insights(post_id, metrics)
        if "error" in raw:
            return raw
        # Zéros explicites : un {} vide était ambigu (aucune réaction vs erreur).
        results: dict[str, Any] = {name: 0 for name in metrics}
        for item in raw.get("data", []):
            name = item.get("name")
            value = item.get("values", [{}])[0].get("value")
            results[name] = value
        return results

    def bulk_delete_comments(self, comment_ids: list[str]) -> list[dict[str, Any]]:
        """Delete multiple comments and return their results."""
        results = []
        for cid in comment_ids:
            res = self.api.delete_comment(cid)
            results.append({"comment_id": cid, "result": res})
        return results

    def bulk_hide_comments(self, comment_ids: list[str]) -> list[dict[str, Any]]:
        """Hide multiple comments and return their results."""
        results = []
        for cid in comment_ids:
            res = self.api.hide_comment(cid)
            results.append({"comment_id": cid, "result": res})
        return results

    def bulk_unhide_comments(self, comment_ids: list[str]) -> list[dict[str, Any]]:
        """Unhide multiple comments and return their results."""
        results = []
        for cid in comment_ids:
            res = self.api.unhide_comment(cid)
            results.append({"comment_id": cid, "result": res})
        return results

    def get_comment_replies(self, comment_id: str) -> dict[str, Any]:
        return self.api.get_comment_replies(comment_id)

    def get_post_permalink(self, post_id: str) -> dict[str, Any]:
        return self.api.get_post_permalink(post_id)

    def get_scheduled_posts(self) -> dict[str, Any]:
        return self.api.get_scheduled_posts()

    def get_page_info(self) -> dict[str, Any]:
        return self.api.get_page_info()
