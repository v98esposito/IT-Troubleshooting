from datetime import datetime
import enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager


class UserRole(enum.Enum):
    USER = "User"
    MANAGER = "Manager"
    IT = "IT"
    ADMIN = "Admin"


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.USER, nullable=False)
    department = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    created_tickets = db.relationship('Ticket', backref='creator', foreign_keys='Ticket.creator_id', lazy='dynamic')
    assigned_tickets = db.relationship('Ticket', backref='assignee', foreign_keys='Ticket.assignee_id', lazy='dynamic')
    approved_tickets = db.relationship('Ticket', backref='approver', foreign_keys='Ticket.approver_id', lazy='dynamic')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == UserRole.ADMIN

    def is_it(self):
        return self.role == UserRole.IT or self.role == UserRole.ADMIN

    def is_manager(self):
        return self.role == UserRole.MANAGER or self.role == UserRole.ADMIN

    def __repr__(self):
        return f'<User {self.username}>'


# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class TicketStatus(enum.Enum):
    NEW = "New"
    AWAITING_APPROVAL = "Awaiting Approval"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In Progress"
    WAITING_USER = "Waiting for User"
    RESOLVED = "Resolved"
    CLOSED = "Closed"


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    requires_approval = db.Column(db.Boolean, default=False)
    tickets = db.relationship('Ticket', backref='category_rel', lazy='dynamic')

    def __repr__(self):
        return f'<Category {self.name}>'


class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.Enum(TicketStatus), default=TicketStatus.NEW)
    
    # Foreign keys
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    assignee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    
    # Relationships
    comments = db.relationship('Comment', backref='ticket', cascade='all, delete-orphan', lazy='dynamic')
    attachments = db.relationship('Attachment', backref='ticket', cascade='all, delete-orphan', lazy='dynamic')

    def requires_approval(self):
        return self.category_rel.requires_approval

    def can_be_approved_by(self, user):
        return user.is_manager() and self.status == TicketStatus.AWAITING_APPROVAL

    def can_be_assigned_by(self, user):
        return (user.is_manager() or user.is_it()) and self.status == TicketStatus.APPROVED

    def can_be_updated_by(self, user):
        return (user.id == self.creator_id or 
                user.id == self.assignee_id or 
                user.is_admin() or 
                (user.is_it() and self.status in [TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_USER]))

    def __repr__(self):
        return f'<Ticket {self.id}: {self.title}>'


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    internal_only = db.Column(db.Boolean, default=False)
    
    # Foreign keys
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    def __repr__(self):
        return f'<Comment {self.id} for Ticket {self.ticket_id}>'


class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    file_path = db.Column(db.String(255), nullable=False)
    
    # Foreign keys
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'), nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationship to the user who uploaded the file
    uploader = db.relationship('User', backref='attachments')
    
    def __repr__(self):
        return f'<Attachment {self.filename} for Ticket {self.ticket_id}>'
