
from django.db import models
from django.conf import settings

class Conversation(models.Model):
    # Link a conversation to a user account (if logged in).
    # getattr(...) safely gets AUTH_USER_MODEL; if missing, falls back to "auth.User".
    user = models.ForeignKey(
        getattr(settings, "AUTH_USER_MODEL", "auth.User"),
        null=True, blank=True,                 # allow this to be empty (for anonymous users)
        on_delete=models.SET_NULL              # if the user is deleted, keep the conversation but set user=None
    )

    # For anonymous visitors: store Django's session key so we can group their messages.
    session_key = models.CharField(max_length=64, blank=True, default="")

    # Human-friendly title for the conversation (shown in admin/UI)
    title = models.CharField(max_length=200, blank=True, default="Conversation")

    # Timestamp automatically set when the row is first created
    created_at = models.DateTimeField(auto_now_add=True)

    # How this object is displayed (e.g., in Django admin or shell)
    def __str__(self):
        return self.title or f"Conv {self.pk}"


class Message(models.Model):
    # Each message belongs to a Conversation.
    # related_name="messages" lets you do conversation.messages.all()
    # If a conversation is deleted, delete its messages too.
    conversation = models.ForeignKey(
        Conversation, related_name="messages", on_delete=models.CASCADE
    )

    # Who sent it: "user" (the person) or "assistant" (your bot)
    role = models.CharField(
        max_length=10,
        choices=[("user", "user"), ("assistant", "assistant")]
    )

    # The actual text content of the message
    content = models.TextField()

    # Set when the message row is created
    created_at = models.DateTimeField(auto_now_add=True)



