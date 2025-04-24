from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, BooleanField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from models import User, UserRole, TicketStatus, Category
from app import db


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    department = StringField('Department', validators=[Optional(), Length(max=120)])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username is already taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email is already registered. Please use a different one.')


class TicketForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[DataRequired()])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()], render_kw={"class": "form-select"})
    attachment = FileField('Attachment', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'], 'Images, PDFs, and documents only!')
    ])
    submit = SubmitField('Submit Ticket')

    def __init__(self, *args, **kwargs):
        super(TicketForm, self).__init__(*args, **kwargs)
        self.category_id.choices = [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]


class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[DataRequired()])
    internal_only = BooleanField('Internal Only (not visible to users)')
    attachment = FileField('Attachment', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'], 'Images, PDFs, and documents only!')
    ])
    submit = SubmitField('Add Comment')


class TicketActionForm(FlaskForm):
    action = HiddenField('Action', validators=[DataRequired()])
    ticket_id = HiddenField('Ticket ID', validators=[DataRequired()])
    submit = SubmitField('Submit')


class AssignTicketForm(FlaskForm):
    assignee_id = SelectField('Assign To', coerce=int, validators=[DataRequired()], render_kw={"class": "form-select"})
    submit = SubmitField('Assign Ticket')

    def __init__(self, *args, **kwargs):
        super(AssignTicketForm, self).__init__(*args, **kwargs)
        # Get all IT members
        self.assignee_id.choices = [(u.id, u.username) for u in 
                                    User.query.filter(User.role == UserRole.IT).order_by(User.username).all()]


class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description')
    requires_approval = BooleanField('Requires Manager Approval')
    submit = SubmitField('Save Category')

    def validate_name(self, name):
        if self.original_name and self.original_name.data != name.data:
            category = Category.query.filter_by(name=name.data).first()
            if category:
                raise ValidationError('Category name already exists.')
        elif not self.original_name:
            category = Category.query.filter_by(name=name.data).first()
            if category:
                raise ValidationError('Category name already exists.')

    def __init__(self, *args, **kwargs):
        super(CategoryForm, self).__init__(*args, **kwargs)
        self.original_name = None


class UserManagementForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    role = SelectField('Role', choices=[(role.name, role.value) for role in UserRole],
                      validators=[DataRequired()], render_kw={"class": "form-select"})
    department = StringField('Department', validators=[Optional(), Length(max=120)])
    is_active = BooleanField('Active')
    submit = SubmitField('Save User')

    def validate_username(self, username):
        if hasattr(self, 'original_username') and self.original_username and self.original_username != username.data:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('Username is already taken.')
        elif not hasattr(self, 'original_username'):
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('Username is already taken.')

    def validate_email(self, email):
        if hasattr(self, 'original_email') and self.original_email and self.original_email != email.data:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('Email is already registered.')
        elif not hasattr(self, 'original_email'):
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('Email is already registered.')


class FilterTicketsForm(FlaskForm):
    status = SelectField('Status', choices=[('all', 'All')], validators=[Optional()], render_kw={"class": "form-select"})
    category = SelectField('Category', choices=[('all', 'All')], validators=[Optional()], render_kw={"class": "form-select"})
    submit = SubmitField('Filter')

    def __init__(self, *args, **kwargs):
        super(FilterTicketsForm, self).__init__(*args, **kwargs)
        # Add all statuses to choices
        status_choices = [('all', 'All')]
        status_choices.extend([(status.name, status.value) for status in TicketStatus])
        self.status.choices = status_choices
        
        # Add all categories to choices
        category_choices = [('all', 'All')]
        category_choices.extend([(str(c.id), c.name) for c in Category.query.order_by(Category.name).all()])
        self.category.choices = category_choices
