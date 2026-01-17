from flask import current_app, flash, render_template, request
from flask_login import current_user

from src import db
from src.contact.forms import ContactForm
from src.extensions.extension_utils import safe_get_notif_sender
from src.models.contact_form_entries import ContactFormEntries


def load_contact_us_page(contact_form: ContactForm, contacted: bool = False) -> str:
    return render_template(
        "pages/contact_us.html",
        contact_form=contact_form,
        is_contact_form=True,
        contacted=contacted,
    )


def validate_and_contact(contact_form: ContactForm) -> str:
    subject = contact_form.subject.get()
    content = contact_form.content.get()

    # Parse the user agent string to get OS, browser, version
    user_agent = request.user_agent.string

    contact_form_entry = ContactFormEntries(
        subject=subject, content=content, user_agent=user_agent
    )

    db.session.add(contact_form_entry)
    db.session.commit()

    notification_sender = safe_get_notif_sender(current_app)

    message_delivered = notification_sender.send_contact_form_details(
        subject=subject,
        content=content,
        contact_id=contact_form_entry.id,
        username=(
            current_user.username if contact_form_entry.user_id is not None else None
        ),
    )

    if message_delivered:
        contact_form_entry.delivered = True
        db.session.commit()

    flash("Sent! Thanks for reaching out.")
    return load_contact_us_page(contact_form, contacted=True)
