from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, SelectField, TextAreaField, BooleanField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from models import User, UserRole, TicketStatus, Category, Department
from extensions import db


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    department_id = SelectField('Dipartimento', coerce=int, validators=[Optional()], render_kw={"class": "form-select"})
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username is already taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email is already registered. Please use a different one.')
            
    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        self.department_id.choices = [(d.id, d.name) for d in Department.query.order_by(Department.name).all()]
        self.department_id.choices.insert(0, (0, 'Seleziona un dipartimento'))


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


class DepartmentForm(FlaskForm):
    name = StringField('Nome Dipartimento', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Descrizione')
    submit = SubmitField('Salva Dipartimento')

    def validate_name(self, name):
        if self.original_name and self.original_name.data != name.data:
            department = Department.query.filter_by(name=name.data).first()
            if department:
                raise ValidationError('Il nome del dipartimento esiste già.')
        elif not self.original_name:
            department = Department.query.filter_by(name=name.data).first()
            if department:
                raise ValidationError('Il nome del dipartimento esiste già.')

    def __init__(self, *args, **kwargs):
        super(DepartmentForm, self).__init__(*args, **kwargs)
        self.original_name = None


class UserManagementForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    role = SelectField('Role', choices=[(role.name, role.value) for role in UserRole],
                      validators=[DataRequired()], render_kw={"class": "form-select"})
    department_id = SelectField('Dipartimento', coerce=int, validators=[Optional()], render_kw={"class": "form-select"})
    is_active = BooleanField('Active')
    submit = SubmitField('Save User')

    def __init__(self, *args, **kwargs):
        super(UserManagementForm, self).__init__(*args, **kwargs)
        self.department_id.choices = [(d.id, d.name) for d in Department.query.order_by(Department.name).all()]
        self.department_id.choices.insert(0, (0, 'Nessun dipartimento'))


class FilterTicketsForm(FlaskForm):
    status = SelectField('Status', choices=[(status.name, status.value) for status in TicketStatus])
    category = SelectField('Category')
    department = SelectField('Dipartimento')
    submit = SubmitField('Filter')

    def __init__(self, *args, **kwargs):
        super(FilterTicketsForm, self).__init__(*args, **kwargs)
        self.status.choices.insert(0, ('all', 'All Statuses'))
        self.category.choices = [(str(c.id), c.name) for c in Category.query.order_by(Category.name).all()]
        self.category.choices.insert(0, ('all', 'All Categories'))
        self.department.choices = [(str(d.id), d.name) for d in Department.query.order_by(Department.name).all()]
        self.department.choices.insert(0, ('all', 'All Departments'))