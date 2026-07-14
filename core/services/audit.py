"""Audit trail helper used by every coach/administrator mutation."""


def record_change(*, changed_by, affected_user, obj, field, previous, new, reason=""):
    from core.models import AuditRecord

    return AuditRecord.objects.create(
        changed_by=changed_by if getattr(changed_by, "pk", None) else None,
        affected_user=affected_user,
        object_type=type(obj).__name__,
        object_id=str(getattr(obj, "pk", "") or ""),
        field_changed=field,
        previous_value="" if previous is None else str(previous),
        new_value="" if new is None else str(new),
        reason=reason or "",
    )


def record_form_changes(*, changed_by, affected_user, form, reason=""):
    """Audit every changed field of a saved ModelForm."""
    records = []
    obj = form.instance
    for field in form.changed_data:
        previous = form.initial.get(field, "")
        new = form.cleaned_data.get(field, "")
        records.append(
            record_change(
                changed_by=changed_by, affected_user=affected_user, obj=obj,
                field=field, previous=previous, new=new, reason=reason,
            )
        )
    return records
