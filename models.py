from datetime import datetime
import enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db, login_manager
#from app import db, login_manager


class UserRole(enum.Enum):
    USER = "User"
    DEPT_MANAGER = "Department Manager"
    MANAGER = "Manager"
    IT = "IT"
    ADMIN = "Admin"


class Department(db.Model):
    __tablename__ = 'department'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)
    users = db.relationship('User', backref='department_rel', foreign_keys='User.department_id', lazy='dynamic')
    managed_by = db.relationship('User', backref='managed_department_rel', foreign_keys='User.managed_department_id', uselist=False)
    
    def __repr__(self):
        return f'<Department {self.name}>'


class User(UserMixin, db.Model):
    __tablename__ = 'user'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.USER, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    managed_department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
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

    def is_dept_manager(self):
        return self.role == UserRole.DEPT_MANAGER or self.role == UserRole.ADMIN
    
    def is_manager(self):
        return self.role == UserRole.MANAGER or self.role == UserRole.ADMIN
    
    def is_any_manager(self):
        return self.role in [UserRole.DEPT_MANAGER, UserRole.MANAGER, UserRole.ADMIN]

    def __repr__(self):
        return f'<User {self.username}>'


class PasswordReset(db.Model):
    __tablename__ = 'password_reset'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    must_change = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('password_reset_rel', uselist=False))

    def __repr__(self):
        return f'<PasswordReset user_id={self.user_id} must_change={self.must_change}>'


# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class TicketStatus(enum.Enum):
    NEW = "New"
    AWAITING_DEPT_MANAGER_APPROVAL = "Awaiting Department Manager Approval"
    REJECTED_BY_DEPT_MANAGER = "Rejected by Department Manager"
    AWAITING_IT_MANAGER_APPROVAL = "Awaiting IT Manager Approval"
    AWAITING_APPROVAL = "Awaiting Approval"  # Mantenuto per compatibilità
    APPROVED = "Approved"
    REJECTED = "Rejected"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In Progress"
    WAITING_USER = "Waiting for User"
    PENDING = "In Sospeso"
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
    dept_manager_approver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=True)
    
    # Relationships
    comments = db.relationship('Comment', backref='ticket', cascade='all, delete-orphan', lazy='dynamic')
    attachments = db.relationship('Attachment', backref='ticket', cascade='all, delete-orphan', lazy='dynamic')

    def requires_approval(self):
        return self.category_rel.requires_approval

    def can_be_approved_by_dept_manager(self, user):
        return (user.is_dept_manager() and 
                self.status == TicketStatus.AWAITING_DEPT_MANAGER_APPROVAL and
                user.managed_department_id == self.department_id)
    
    def can_be_approved_by_it_manager(self, user):
        return user.is_manager() and self.status == TicketStatus.AWAITING_IT_MANAGER_APPROVAL
    
    def can_be_approved_by(self, user):
        return (self.can_be_approved_by_dept_manager(user) or 
                self.can_be_approved_by_it_manager(user) or
                (user.is_manager() and self.status == TicketStatus.AWAITING_APPROVAL))

    def can_be_assigned_by(self, user):
        return (user.is_manager() or user.is_it()) and self.status == TicketStatus.APPROVED

    def can_be_updated_by(self, user):
        return (user.id == self.creator_id or 
                user.id == self.assignee_id or 
                user.is_admin() or 
                (user.is_it() and self.status in [TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_USER, TicketStatus.PENDING]) or
                (user.is_manager() and self.status in [TicketStatus.APPROVED, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_USER, TicketStatus.PENDING, TicketStatus.RESOLVED]))

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
