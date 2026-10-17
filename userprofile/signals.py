from anymail.signals import EventType, tracking
from django.dispatch import receiver

from .models import EmailSuppression


def should_suppress(event):
    """Spam complaints, or any bounce after which Postmark deactivated the address.
    Soft bounces (full mailbox, etc.) leave the address active and are ignored."""
    if event.event_type == EventType.COMPLAINED:
        return True
    esp_event = event.esp_event if isinstance(event.esp_event, dict) else {}
    return bool(esp_event.get("Inactive"))


@receiver(tracking)
def suppress_bad_addresses(sender, event, esp_name, **kwargs):
    """Record addresses the email provider says we should stop emailing."""
    if not event.recipient or not should_suppress(event):
        return
    EmailSuppression.objects.update_or_create(
        email=event.recipient.lower(),
        defaults={
            "reason": event.event_type,
            "description": event.description or event.reject_reason or "",
        },
    )
