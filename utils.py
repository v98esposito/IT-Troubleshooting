import os
import secrets
from datetime import datetime
from flask import current_app
from flask_mail import Message
from werkzeug.utils import secure_filename
from app import mail
from models import Ticket, User, TicketStatus


def save_attachment(file):
    """Save an uploaded file to the uploads directory with a secure filename"""
    if not file:
        return None
    
    # Generate a secure filename to prevent directory traversal attacks
    random_hex = secrets.token_hex(8)
    _, file_extension = os.path.splitext(file.filename)
    secure_name = secure_filename(file.filename)
    filename = random_hex + file_extension
    
    # Create upload path if it doesn't exist
    upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'])
    if not os.path.exists(upload_path):
        os.makedirs(upload_path)
    
    # Save the file
    file_path = os.path.join(upload_path, filename)
    file.save(file_path)
    
    return {
        'original_filename': secure_name,
        'saved_filename': filename,
        'file_path': file_path
    }


def get_ticket_status_counts():
    """Get counts of tickets by status for reporting"""
    status_counts = {}
    for status in TicketStatus:
        count = Ticket.query.filter_by(status=status).count()
        status_counts[status.value] = count
    return status_counts


def get_tickets_by_category():
    """Get counts of tickets by category for reporting"""
    from sqlalchemy import func
    from models import Category
    
    results = db.session.query(
        Category.name, 
        func.count(Ticket.id)
    ).join(
        Ticket, 
        Category.id == Ticket.category_id
    ).group_by(
        Category.name
    ).all()
    
    return {category: count for category, count in results}


def send_notification_email(recipients, subject, template):
    """Send notification email to recipients"""
    if not recipients:
        return False
    
    if isinstance(recipients, str):
        recipients = [recipients]
    
    try:
        msg = Message(
            subject,
            recipients=recipients,
            html=template,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        mail.send(msg)
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {str(e)}")
        return False


def notify_ticket_created(ticket):
    """Send notification when a ticket is created"""
    # Notify IT team and managers if approvals needed
    if ticket.requires_approval():
        managers = User.query.filter_by(role='MANAGER').all()
        recipients = [manager.email for manager in managers]
    else:
        it_team = User.query.filter_by(role='IT').all()
        recipients = [it_member.email for it_member in it_team]
    
    subject = f"New Ticket Created: {ticket.title}"
    template = f"""
    <h2>New Ticket #{ticket.id}: {ticket.title}</h2>
    <p><strong>Created by:</strong> {ticket.creator.username}</p>
    <p><strong>Category:</strong> {ticket.category_rel.name}</p>
    <p><strong>Status:</strong> {ticket.status.value}</p>
    <p><strong>Description:</strong><br>{ticket.description}</p>
    """
    
    # Also notify the creator
    send_notification_email(ticket.creator.email, f"Your ticket #{ticket.id} has been created", template)
    
    return send_notification_email(recipients, subject, template)


def notify_ticket_status_change(ticket, previous_status):
    """Send notification when a ticket's status changes"""
    recipients = [ticket.creator.email]
    
    if ticket.assignee:
        recipients.append(ticket.assignee.email)
    
    subject = f"Ticket #{ticket.id} Status Updated: {ticket.status.value}"
    template = f"""
    <h2>Ticket #{ticket.id}: {ticket.title}</h2>
    <p>Status changed from <strong>{previous_status.value}</strong> to <strong>{ticket.status.value}</strong></p>
    <p><strong>Category:</strong> {ticket.category_rel.name}</p>
    <p><strong>Description:</strong><br>{ticket.description}</p>
    """
    
    return send_notification_email(recipients, subject, template)


def notify_ticket_comment(ticket, comment):
    """Send notification when a comment is added to a ticket"""
    recipients = [ticket.creator.email]
    
    if ticket.assignee and ticket.assignee.id != comment.author_id:
        recipients.append(ticket.assignee.email)
    
    # Don't send internal comments to users
    if comment.internal_only and ticket.creator.role == 'USER':
        recipients.remove(ticket.creator.email)
    
    subject = f"New Comment on Ticket #{ticket.id}"
    template = f"""
    <h2>New Comment on Ticket #{ticket.id}: {ticket.title}</h2>
    <p><strong>From:</strong> {comment.author.username}</p>
    <p><strong>Comment:</strong><br>{comment.content}</p>
    """
    
    return send_notification_email(recipients, subject, template)


def notify_ticket_assigned(ticket):
    """Send notification when a ticket is assigned"""
    if not ticket.assignee:
        return False
    
    recipients = [ticket.assignee.email, ticket.creator.email]
    
    subject = f"Ticket #{ticket.id} Assigned to {ticket.assignee.username}"
    template = f"""
    <h2>Ticket #{ticket.id}: {ticket.title}</h2>
    <p>This ticket has been assigned to <strong>{ticket.assignee.username}</strong></p>
    <p><strong>Category:</strong> {ticket.category_rel.name}</p>
    <p><strong>Status:</strong> {ticket.status.value}</p>
    <p><strong>Description:</strong><br>{ticket.description}</p>
    """
    
    return send_notification_email(recipients, subject, template)
