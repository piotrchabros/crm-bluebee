"""Keep the two account<->contact relationships in sync.

A contact can be linked to a company two ways:
  * ``Contact.account``            -- FK ("primary account", single)
  * ``Account.contacts``           -- M2M (related_name="account_contacts")

Historically a write to one side did not touch the other, so the company's
Contacts tab (which reads the M2M) and the contact's Company dropdown (which
sets the FK) could disagree. These signals mirror one onto the other under a
"single primary account per contact" rule: a contact's M2M membership is always
exactly {its account} (or empty).
"""

from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from accounts.models import Account
from contacts.models import Contact


@receiver(post_save, sender=Contact)
def mirror_contact_fk_to_m2m(sender, instance, **kwargs):
    """FK -> M2M. Contact belongs to exactly its account (0 or 1).

    ``.set()`` on the reverse accessor fires m2m_changed with ``reverse=True``,
    which the handler below ignores, so there is no recursion.
    """
    target = [instance.account] if instance.account_id else []
    instance.account_contacts.set(target)


@receiver(m2m_changed, sender=Account.contacts.through)
def mirror_m2m_to_contact_fk(sender, instance, action, pk_set, reverse, **kwargs):
    """M2M -> FK. Only react to forward changes (account.contacts add/remove/clear);
    the reverse direction is already driven by the FK mirror above."""
    if reverse:
        return
    if action == "post_add":
        # Saving each contact runs the FK->M2M mirror, which normalises the
        # contact to a single account (removing any stale membership). save()
        # fires post_save; the resulting .set() only removes rows, so it never
        # re-enters this forward handler.
        for contact in Contact.objects.filter(pk__in=pk_set or []).exclude(
            account=instance
        ):
            contact.account_id = instance.pk
            contact.save(update_fields=["account"])
    elif action == "post_remove":
        # QuerySet.update() bypasses post_save -> no signal churn.
        Contact.objects.filter(pk__in=pk_set or [], account=instance).update(
            account=None
        )
    elif action == "post_clear":
        Contact.objects.filter(account=instance).update(account=None)
