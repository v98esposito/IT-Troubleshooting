import os
from datetime import datetime
from flask import render_template, flash, redirect, url_for, request, abort, send_from_directory
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_, and_

from extensions import db
from app import app, db
from models import User, UserRole, Ticket, TicketStatus, Comment, Attachment, Category, Department

from forms import (LoginForm, RegistrationForm, TicketForm, CommentForm, 
                   TicketActionForm, AssignTicketForm, CategoryForm, 
                   UserManagementForm, FilterTicketsForm, DepartmentForm,
                   AdminPasswordResetForm)
from utils import (save_attachment, notify_ticket_created, notify_ticket_status_change,
                  notify_ticket_comment, notify_ticket_assigned, get_ticket_status_counts)


def init_default_data():
    """Initialize default data if not exists"""
    # Create default categories if none exist
    if Category.query.count() == 0:
        default_categories = [
            {"name": "Hardware Issue", "description": "Problems with physical hardware", "requires_approval": True},
            {"name": "Software Issue", "description": "Problems with software applications", "requires_approval": True},
            {"name": "Network Issue", "description": "Problems with network connectivity", "requires_approval": True},
            {"name": "Account Access", "description": "Issues with account access or permissions", "requires_approval": True},
            {"name": "Service Request", "description": "Request for new services or equipment", "requires_approval": True}
        ]
        
        for cat in default_categories:
            category = Category(
                name=cat["name"],
                description=cat["description"],
                requires_approval=cat["requires_approval"]
            )
            db.session.add(category)
        
        db.session.commit()
    
    # Create default departments if none exist
    if Department.query.count() == 0:
        default_departments = [
            {"name": "IT Department", "description": "Information Technology Department"},
            {"name": "Marketing", "description": "Marketing Department"},
            {"name": "Operations", "description": "Operations Department"}
        ]
        
        departments = {}
        for dept in default_departments:
            department = Department(
                name=dept["name"],
                description=dept["description"]
            )
            db.session.add(department)
            departments[dept["name"]] = department
        
        db.session.commit()
    else:
        # Recupera i dipartimenti esistenti
        departments = {dept.name: dept for dept in Department.query.all()}
    
    # Create admin user if no users exist
    if User.query.count() == 0:
        admin = User(
            username="admin",
            email="admin@example.com",
            role=UserRole.ADMIN,
            department_id=departments.get("IT Department").id if "IT Department" in departments else None
        )
        admin.set_password("admin123")  # In production, use a secure password
        db.session.add(admin)
        
        # Create a user for each role
        user = User(
            username="user",
            email="user@example.com",
            role=UserRole.USER,
            department_id=departments.get("Marketing").id if "Marketing" in departments else None
        )
        user.set_password("user123")
        db.session.add(user)
        
        # Create Department Manager
        dept_manager = User(
            username="dept_manager",
            email="dept_manager@example.com",
            role=UserRole.DEPT_MANAGER,
            department_id=departments.get("Marketing").id if "Marketing" in departments else None,
            managed_department_id=departments.get("Marketing").id if "Marketing" in departments else None
        )
        dept_manager.set_password("dept123")
        db.session.add(dept_manager)
        
        # Create IT Manager
        manager = User(
            username="it_manager",
            email="it_manager@example.com",
            role=UserRole.MANAGER,
            department_id=departments.get("IT Department").id if "IT Department" in departments else None
        )
        manager.set_password("manager123")
        db.session.add(manager)
        
        it_user = User(
            username="it_support",
            email="it@example.com",
            role=UserRole.IT,
            department_id=departments.get("IT Department").id if "IT Department" in departments else None
        )
        it_user.set_password("it123")
        db.session.add(it_user)
        
        db.session.commit()


def register_routes(app):
    # Initialize default data
    with app.app_context():
        init_default_data()
    
    # Add template context processor for global variables
    @app.context_processor
    def inject_now():
        return {'now': datetime.now()}
    
    # Add custom Jinja2 filters
    @app.template_filter('nl2br')
    def nl2br_filter(text):
        if not text:
            return ""
        return text.replace('\n', '<br>')
    
    # Authentication routes
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.before_request
    def enforce_password_change():
        from models import PasswordReset
        # Forza il cambio password se marcati must_change
        if current_user.is_authenticated:
            pr = PasswordReset.query.filter_by(user_id=current_user.id, must_change=True).first()
            allowed_endpoints = {'change_password', 'logout', 'static', 'login'}
            if pr and request.endpoint not in allowed_endpoints:
                return redirect(url_for('change_password'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            
            if user and user.check_password(form.password.data):
                login_user(user)
                next_page = request.args.get('next')
                flash('Login successful!', 'success')
                return redirect(next_page or url_for('dashboard'))
            else:
                flash('Login failed. Please check your email and password.', 'danger')
        
        return render_template('login.html', form=form)

    @app.route('/change_password', methods=['GET', 'POST'])
    @login_required
    def change_password():
        from models import PasswordReset
        from forms import ChangePasswordForm

        form = ChangePasswordForm()
        if form.validate_on_submit():
            # Verifica vecchia password
            if not current_user.check_password(form.old_password.data):
                flash('La vecchia password non è corretta.', 'danger')
            else:
                # Imposta nuova password
                current_user.set_password(form.new_password.data)
                db.session.commit()

                # Pulisce il flag must_change se presente
                pr = PasswordReset.query.filter_by(user_id=current_user.id).first()
                if pr:
                    db.session.delete(pr)
                    db.session.commit()

                flash('Password aggiornata con successo.', 'success')
                return redirect(url_for('dashboard'))

        return render_template('change_password.html', form=form)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        form = RegistrationForm()
        if form.validate_on_submit():
            user = User(
                username=form.username.data,
                email=form.email.data,
                department_id=form.department_id.data if form.department_id.data else None,
                role=UserRole.USER  # Default role is USER
            )
            user.set_password(form.password.data)
            
            db.session.add(user)
            db.session.commit()
            
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('login'))
        
        return render_template('register.html', form=form)

    @app.route('/logout')
    def logout():
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('login'))

    # Dashboard route
    @app.route('/dashboard')
    @login_required
    def dashboard():
        user_role = current_user.role
        
        # Get recent tickets based on user role
        if user_role == UserRole.USER:
            recent_tickets = Ticket.query.filter_by(creator_id=current_user.id).order_by(Ticket.created_at.desc()).limit(5).all()
            tickets_await_action = Ticket.query.filter_by(creator_id=current_user.id, status=TicketStatus.WAITING_USER).all()
        
        elif current_user.role == UserRole.DEPT_MANAGER:
            # Department Managers see tickets pending their approval from their department
            recent_tickets = Ticket.query.filter(
                and_(
                    Ticket.department_id == current_user.managed_department_id,
                    Ticket.status == TicketStatus.AWAITING_DEPT_MANAGER_APPROVAL
                )
            ).order_by(Ticket.created_at.desc()).limit(5).all()
            
            tickets_await_action = Ticket.query.filter(
                and_(
                    Ticket.department_id == current_user.managed_department_id,
                    Ticket.status == TicketStatus.AWAITING_DEPT_MANAGER_APPROVAL
                )
            ).all()
        
        elif current_user.role == UserRole.MANAGER:
            # IT Managers see tickets pending IT approval
            recent_tickets = Ticket.query.filter(
                Ticket.status == TicketStatus.AWAITING_IT_MANAGER_APPROVAL
            ).order_by(Ticket.created_at.desc()).limit(5).all()
            
            tickets_await_action = Ticket.query.filter_by(status=TicketStatus.AWAITING_IT_MANAGER_APPROVAL).all()
        
        elif user_role == UserRole.IT:
            # IT team sees assigned tickets and unassigned approved tickets
            recent_tickets = Ticket.query.filter(
                or_(
                    Ticket.assignee_id == current_user.id,
                    and_(
                        Ticket.assignee_id == None,
                        Ticket.status == TicketStatus.APPROVED
                    )
                )
            ).order_by(Ticket.created_at.desc()).limit(5).all()
            
            tickets_await_action = Ticket.query.filter(
                or_(
                    and_(
                        Ticket.assignee_id == current_user.id,
                        Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS])
                    ),
                    and_(
                        Ticket.assignee_id == None,
                        Ticket.status == TicketStatus.APPROVED
                    )
                )
            ).all()
        
        else:  # ADMIN
            recent_tickets = Ticket.query.order_by(Ticket.created_at.desc()).limit(5).all()
            tickets_await_action = Ticket.query.filter(
                Ticket.status.in_([
                    TicketStatus.NEW, 
                    TicketStatus.AWAITING_APPROVAL, 
                    TicketStatus.AWAITING_DEPT_MANAGER_APPROVAL,
                    TicketStatus.AWAITING_IT_MANAGER_APPROVAL,
                    TicketStatus.APPROVED, 
                    TicketStatus.ASSIGNED
                ])
            ).all()
        
        # Get stats for reporting
        status_counts = get_ticket_status_counts()
        
        return render_template(
            'dashboard.html',
            recent_tickets=recent_tickets,
            tickets_await_action=tickets_await_action,
            status_counts=status_counts
        )
    
    # Department Manager Dashboard
    @app.route('/department_manager_dashboard')
    @login_required
    def department_manager_dashboard():
        if not current_user.is_dept_manager():
            abort(403)
        
        # Get tickets pending department manager approval from their department
        pending_tickets = Ticket.query.filter(
            and_(
                Ticket.department_id == current_user.managed_department_id,
                Ticket.status == TicketStatus.AWAITING_DEPT_MANAGER_APPROVAL
            )
        ).order_by(Ticket.created_at.desc()).all()
        
        # Get department statistics
        dept_stats = {
            'pending_approval': len(pending_tickets),
            'approved_this_month': Ticket.query.filter(
                and_(
                    Ticket.department_id == current_user.managed_department_id,
                    Ticket.dept_manager_approver_id == current_user.id,
                    Ticket.created_at >= datetime.now().replace(day=1)
                )
            ).count(),
            'rejected_this_month': Ticket.query.filter(
                and_(
                    Ticket.department_id == current_user.managed_department_id,
                    Ticket.status == TicketStatus.REJECTED_BY_DEPT_MANAGER,
                    Ticket.dept_manager_approver_id == current_user.id,
                    Ticket.created_at >= datetime.now().replace(day=1)
                )
            ).count()
        }
        
        return render_template(
            'manager/dept_manager_dashboard.html',
            pending_tickets=pending_tickets,
            dept_stats=dept_stats
        )

    # IT Manager Approvals
    @app.route('/manager/approvals')
    @login_required
    def approvals():
        if not current_user.is_manager():
            abort(403)
        
        # Get tickets pending IT manager approval (AWAITING_IT_MANAGER_APPROVAL)
        tickets = Ticket.query.filter_by(
            status=TicketStatus.AWAITING_IT_MANAGER_APPROVAL
        ).order_by(Ticket.created_at.desc()).all()
        
        # Get approved but unassigned tickets (già approvati, in attesa di assegnazione)
        unassigned_tickets = Ticket.query.filter_by(
            status=TicketStatus.APPROVED,
            assignee_id=None
        ).order_by(Ticket.created_at.desc()).all()
        
        # Lista IT staff e workload per il modal di assegnazione
        it_users = User.query.filter_by(role=UserRole.IT, is_active=True).all()
        workload_data = {}
        for staff in it_users:
            workload_data[staff.id] = Ticket.query.filter(
                Ticket.assignee_id == staff.id,
                Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_USER])
            ).count()
        
        return render_template(
            'manager/approvals.html',
            tickets=tickets,
            unassigned_tickets=unassigned_tickets,
            it_users=it_users,
            workload_data=workload_data
        )

    
    # Ticket routes
    @app.route('/tickets')
    @login_required
    def ticket_list():
        form = FilterTicketsForm(request.args, meta={'csrf': False})
        
        # Base query
        query = Ticket.query
        
        # Filter by user role
        if current_user.role == UserRole.USER:
            # Users can only see their own tickets
            query = query.filter_by(creator_id=current_user.id)
        
        elif current_user.role == UserRole.DEPT_MANAGER:
            # Department Managers see tickets from their managed department
            query = query.filter(
                Ticket.department_id == current_user.managed_department_id
            )
        
        elif current_user.role == UserRole.MANAGER:
            # IT Managers see tickets pending IT approval and approved tickets
            query = query.filter(
                or_(
                    Ticket.status == TicketStatus.AWAITING_IT_MANAGER_APPROVAL,
                    Ticket.status == TicketStatus.APPROVED,
                    Ticket.status == TicketStatus.ASSIGNED,
                    Ticket.status == TicketStatus.IN_PROGRESS,
                    Ticket.status == TicketStatus.RESOLVED,
                    Ticket.status == TicketStatus.REJECTED,
                    Ticket.status == TicketStatus.CLOSED
                )
            )
        
        elif current_user.role == UserRole.IT:
            # IT team sees assigned tickets and unassigned approved tickets
            query = query.filter(
                or_(
                    Ticket.assignee_id == current_user.id,
                    and_(
                        Ticket.assignee_id == None,
                        Ticket.status.in_([TicketStatus.APPROVED, TicketStatus.NEW])
                    )
                )
            )
        
        # Apply filters
        if form.status.data and form.status.data != 'all':
            query = query.filter(Ticket.status == TicketStatus[form.status.data])
        
        if form.category.data and form.category.data != 'all':
            query = query.filter(Ticket.category_id == int(form.category.data))
        
        # Sort by created date, newest first
        tickets = query.order_by(Ticket.created_at.desc()).all()
        
        return render_template('ticket_list.html', tickets=tickets, form=form)

    @app.route('/tickets/create', methods=['GET', 'POST'])
    @login_required
    def ticket_create():
        form = TicketForm()
        
        if form.validate_on_submit():
            # Create the ticket
            ticket = Ticket(
                title=form.title.data,
                description=form.description.data,
                category_id=form.category_id.data,
                creator_id=current_user.id,
                department_id=current_user.department_id
            )
            
            # Check if the category requires approval
            category = Category.query.get(form.category_id.data)
            if category and category.requires_approval:
                # Workflow con approvazione: prima il Manager di Dipartimento, poi l'IT Manager
                ticket.status = TicketStatus.AWAITING_DEPT_MANAGER_APPROVAL
            else:
                # Workflow senza approvazione del Dept Manager: va direttamente all'IT Manager
                ticket.status = TicketStatus.AWAITING_IT_MANAGER_APPROVAL
            
            db.session.add(ticket)
            db.session.commit()
            
            # Handle file attachment if provided
            attachment_file = form.attachment.data
            if attachment_file:
                file_info = save_attachment(attachment_file)
                if file_info:
                    attachment = Attachment(
                        filename=file_info['original_filename'],
                        file_path=file_info['saved_filename'],
                        ticket_id=ticket.id,
                        uploader_id=current_user.id
                    )
                    db.session.add(attachment)
                    db.session.commit()
            
            # Send notification
            notify_ticket_created(ticket)
            
            flash(f'Ticket #{ticket.id} has been created successfully.', 'success')
            return redirect(url_for('ticket_detail', ticket_id=ticket.id))
        
        categories = Category.query.all()
        categories_dict = {c.id: c.description for c in categories if c.description}
        return render_template('ticket_create.html', form=form, categories_dict=categories_dict)

    @app.route('/tickets/<int:ticket_id>')
    @login_required
    def ticket_detail(ticket_id):
        ticket = Ticket.query.get_or_404(ticket_id)
        
        # Check permission based on user role
        if (current_user.role == UserRole.USER and ticket.creator_id != current_user.id):
            abort(403)  # Forbidden
        
        if (current_user.role == UserRole.DEPT_MANAGER and 
            ticket.department_id != current_user.managed_department_id):
            abort(403)
        
        if (current_user.role == UserRole.MANAGER and 
            ticket.status not in [TicketStatus.AWAITING_IT_MANAGER_APPROVAL, TicketStatus.APPROVED, 
                                 TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED,
                                 TicketStatus.REJECTED, TicketStatus.CLOSED]):
            abort(403)
        
        comment_form = CommentForm()
        action_form = TicketActionForm()
        assign_form = AssignTicketForm()
        
        # Get comments (filter internal comments for regular users)
        if current_user.role == UserRole.USER:
            comments = Comment.query.filter_by(ticket_id=ticket.id, internal_only=False).order_by(Comment.created_at).all()
        else:
            comments = Comment.query.filter_by(ticket_id=ticket.id).order_by(Comment.created_at).all()
        
        # Get IT staff list and their workload for managers
        it_staff_list = []
        workload_data = {}
        if current_user.is_manager() or current_user.is_admin():
            # Get all active IT staff
            it_staff_list = User.query.filter_by(role=UserRole.IT, is_active=True).all()
            
            # Calculate workload for each IT staff member (number of active tickets)
            for staff in it_staff_list:
                active_tickets_count = Ticket.query.filter(
                    Ticket.assignee_id == staff.id,
                    Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_USER])
                ).count()
                workload_data[staff.id] = active_tickets_count
            
        return render_template(
            'ticket_detail.html',
            ticket=ticket,
            comments=comments,
            comment_form=comment_form,
            action_form=action_form,
            assign_form=assign_form,
            it_staff_list=it_staff_list,
            workload_data=workload_data
        )

    @app.route('/tickets/<int:ticket_id>/comment', methods=['POST'])
    @login_required
    def add_comment(ticket_id):
        ticket = Ticket.query.get_or_404(ticket_id)
        form = CommentForm()
        
        if form.validate_on_submit():
            # Check if internal comment is allowed
            internal_only = form.internal_only.data
            if internal_only and current_user.role == UserRole.USER:
                flash('You are not allowed to create internal comments.', 'danger')
                return redirect(url_for('ticket_detail', ticket_id=ticket_id))
            
            # Create comment
            comment = Comment(
                content=form.content.data,
                internal_only=internal_only,
                ticket_id=ticket_id,
                author_id=current_user.id
            )
            db.session.add(comment)
            db.session.commit()
            
            # Handle file attachment if provided
            attachment_file = form.attachment.data
            if attachment_file:
                file_info = save_attachment(attachment_file)
                if file_info:
                    attachment = Attachment(
                        filename=file_info['original_filename'],
                        file_path=file_info['saved_filename'],
                        ticket_id=ticket_id,
                        uploader_id=current_user.id
                    )
                    db.session.add(attachment)
                    db.session.commit()
            
            # Send notification
            notify_ticket_comment(ticket, comment)
            
            flash('Comment added successfully.', 'success')
        
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))

    @app.route('/tickets/<int:ticket_id>/action', methods=['POST'])
    @login_required
    def ticket_action(ticket_id):
        ticket = Ticket.query.get_or_404(ticket_id)
        
        # Ottieni l'azione dal form
        form = TicketActionForm()
        action = request.form.get('action')
        
        if not action:
            flash('Azione non specificata.', 'danger')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
            
        previous_status = ticket.status
        
        print(f"Processing action: {action} for ticket: {ticket_id}")
        
        # Check permissions based on action and user role
        if action == 'approve_dept' and ticket.can_be_approved_by_dept_manager(current_user):
            # Approvazione del Manager di Dipartimento
            ticket.status = TicketStatus.AWAITING_IT_MANAGER_APPROVAL
            ticket.dept_manager_approver_id = current_user.id
            # Aggiungi nota di sistema per l'approvazione del dipartimento
            approval_comment = Comment(
                content=f"Ticket approvato dal Manager di Dipartimento {current_user.username}",
                ticket_id=ticket.id,
                author_id=current_user.id,
                internal_only=True
            )
            db.session.add(approval_comment)
            db.session.commit()
            # INVIO NOTIFICA AL DIRIGENTE IT
            notify_ticket_status_change(ticket, previous_status)
            flash('Ticket approvato. Ora in attesa di approvazione del Dirigente IT.', 'success')
            return redirect(url_for('department_manager_dashboard'))
            
        elif action == 'reject_dept' and ticket.can_be_approved_by_dept_manager(current_user):
            # Rifiuto del Manager di Dipartimento
            ticket.status = TicketStatus.REJECTED_BY_DEPT_MANAGER
            ticket.dept_manager_approver_id = current_user.id
            
            # Aggiungi nota di sistema per il rifiuto del dipartimento
            reject_comment = Comment(
                content=f"Ticket rifiutato dal Manager di Dipartimento {current_user.username}",
                ticket_id=ticket.id,
                author_id=current_user.id,
                internal_only=True
            )
            db.session.add(reject_comment)
            db.session.commit()
            
            flash('Ticket rifiutato.', 'danger')
            return redirect(url_for('department_manager_dashboard'))
            
        elif action == 'approve' and ticket.can_be_approved_by_it_manager(current_user):
            # Verifica se è richiesta l'assegnazione immediata
            assignee_id = request.form.get('assignee_id')
            
            # Se non c'è un assignee_id, mostra la pagina di selezione dello staff IT
            if not assignee_id and not request.form.get('show_assign_modal'):
                # Reindirizza alla pagina di assegnazione
                it_users = User.query.filter_by(role=UserRole.IT, is_active=True).all()
                if not it_users:
                    flash('Non ci sono utenti IT disponibili per l\'assegnazione.', 'warning')
                    return redirect(url_for('approvals'))
                
                return render_template(
                    'manager/approve_modal.html', 
                    ticket=ticket,
                    it_users=it_users
                )
            
            # Aggiorna lo stato del ticket (approvazione IT Manager)
            ticket.status = TicketStatus.APPROVED
            ticket.approver_id = current_user.id
            
            # Aggiungi nota di sistema per l'approvazione IT
            approval_comment = Comment(
                content=f"Ticket approvato dal Dirigente IT {current_user.username}",
                ticket_id=ticket.id,
                author_id=current_user.id,
                internal_only=True
            )
            db.session.add(approval_comment)
            db.session.commit()
            
            # Se è stato selezionato un membro IT, assegna il ticket
            if assignee_id:
                assignee = User.query.get(assignee_id)
                if assignee and assignee.role == UserRole.IT:
                    ticket.assignee_id = assignee.id
                    ticket.status = TicketStatus.ASSIGNED
                    
                    # Aggiungi nota di sistema per l'assegnazione
                    assign_comment = Comment(
                        content=f"Ticket assegnato a {assignee.username} da {current_user.username}",
                        ticket_id=ticket.id,
                        author_id=current_user.id,
                        internal_only=True
                    )
                    db.session.add(assign_comment)
                    db.session.commit()
                    
                    # Invia notifica
                    notify_ticket_assigned(ticket)
                    
                    flash(f'Ticket approvato e assegnato a {assignee.username}.', 'success')
                else:
                    flash('Membro IT selezionato non valido.', 'danger')
            else:
                flash('Ticket approvato. Ora è disponibile per l\'assegnazione.', 'success')
            
            return redirect(url_for('approvals'))
            
        elif action == 'reject' and ticket.can_be_approved_by_it_manager(current_user):
            ticket.status = TicketStatus.REJECTED
            ticket.approver_id = current_user.id
            
            # Aggiungi nota di sistema per il rifiuto
            reject_comment = Comment(
                content=f"Ticket rifiutato da {current_user.username}",
                ticket_id=ticket.id,
                author_id=current_user.id,
                internal_only=True
            )
            db.session.add(reject_comment)
            db.session.commit()
            
            flash('Ticket rifiutato.', 'danger')
            
        elif action == 'complete' and current_user.is_manager():
            # Azione per segnare un ticket come completato direttamente dal manager
            ticket.status = TicketStatus.RESOLVED
            
            # Aggiungi nota di sistema per il completamento
            complete_comment = Comment(
                content=f"Ticket segnato come completato da {current_user.username} (Manager)",
                ticket_id=ticket.id,
                author_id=current_user.id,
                internal_only=False
            )
            db.session.add(complete_comment)
            db.session.commit()
            
            flash('Ticket segnato come completato.', 'success')
            
        elif action == 'start' and (ticket.assignee_id == current_user.id or current_user.is_admin()):
            ticket.status = TicketStatus.IN_PROGRESS
            flash('Ticket marked as in progress.', 'success')
            db.session.commit()
            
        elif action == 'wait_user' and (ticket.assignee_id == current_user.id or current_user.is_admin()):
            ticket.status = TicketStatus.WAITING_USER
            flash('Ticket marked as waiting for user.', 'success')
            db.session.commit()
            
        elif action == 'pending' and (ticket.assignee_id == current_user.id or current_user.is_admin()):
            ticket.status = TicketStatus.PENDING
            flash('Ticket messo in sospeso.', 'success')
            db.session.commit()
            
        elif action == 'resolve' and (ticket.assignee_id == current_user.id or current_user.is_admin()):
            ticket.status = TicketStatus.RESOLVED
            
            # Aggiungi nota di sistema per il completamento
            complete_comment = Comment(
                content=f"Ticket segnato come completato da {current_user.username} (IT Support)",
                ticket_id=ticket.id,
                author_id=current_user.id,
                internal_only=False
            )
            db.session.add(complete_comment)
            db.session.commit()
            
            flash('Ticket segnato come completato.', 'success')
            
        elif action == 'not_completed' and (ticket.assignee_id == current_user.id or current_user.is_admin()):
            ticket.status = TicketStatus.ASSIGNED
            
            # Aggiungi nota di sistema per il problema riscontrato
            problem_comment = Comment(
                content=f"Problema riscontrato da {current_user.username} (IT Support). Il ticket viene riassegnato.",
                ticket_id=ticket.id,
                author_id=current_user.id,
                internal_only=False
            )
            db.session.add(problem_comment)
            db.session.commit()
            
            flash('Problema segnalato con successo. Il ticket è stato riassegnato.', 'warning')
            
        elif action == 'close' and (ticket.creator_id == current_user.id or current_user.is_admin() or current_user.is_manager()):
            if ticket.status == TicketStatus.RESOLVED or current_user.is_manager():
                ticket.status = TicketStatus.CLOSED
                
                # Aggiungi nota di sistema per la chiusura
                close_comment = Comment(
                    content=f"Ticket chiuso da {current_user.username}",
                    ticket_id=ticket.id,
                    author_id=current_user.id,
                    internal_only=True
                )
                db.session.add(close_comment)
                flash('Ticket has been closed.', 'success')
            else:
                flash('Ticket must be resolved before closing.', 'warning')
            db.session.commit()
                
        elif action == 'reopen' and (ticket.creator_id == current_user.id or current_user.is_admin()):
            if ticket.status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
                ticket.status = TicketStatus.ASSIGNED if ticket.assignee_id else TicketStatus.NEW
                flash('Ticket has been reopened.', 'success')
            else:
                flash('Cannot reopen this ticket.', 'warning')
            db.session.commit()
        
        else:
            flash('You do not have permission for this action.', 'danger')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        # Send notification for status change
        if previous_status != ticket.status:
            notify_ticket_status_change(ticket, previous_status)
        
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))

    @app.route('/tickets/<int:ticket_id>/assign', methods=['POST'])
    @login_required
    def assign_ticket(ticket_id):
        ticket = Ticket.query.get_or_404(ticket_id)
        
        # Ottieni direttamente l'assegnee_id dai dati del form post
        assignee_id = request.form.get('assignee_id')
        
        if not assignee_id:
            flash('Nessun membro IT selezionato per l\'assegnazione.', 'danger')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        if not ticket.can_be_assigned_by(current_user):
            flash('Non hai i permessi per assegnare questo ticket.', 'danger')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        assignee_id = int(assignee_id)  # Converti in intero
        assignee = User.query.get(assignee_id)
        
        if not assignee or assignee.role != UserRole.IT:
            flash('Membro IT selezionato non valido.', 'danger')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        ticket.assignee_id = assignee_id
        ticket.status = TicketStatus.ASSIGNED
        db.session.commit()
        
        # Aggiungi una nota di sistema per l'assegnazione
        assign_comment = Comment(
            content=f"Ticket assegnato a {assignee.username} da {current_user.username}",
            ticket_id=ticket.id,
            author_id=current_user.id,
            internal_only=True
        )
        db.session.add(assign_comment)
        db.session.commit()
        
        # Send notification
        notify_ticket_assigned(ticket)
        
        flash(f'Ticket assegnato a {assignee.username}.', 'success')
        
        # Se siamo un manager, torniamo alla lista delle approvazioni
        if current_user.is_manager():
            return redirect(url_for('approvals'))
            
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))

    @app.route('/tickets/<int:ticket_id>/reassign', methods=['POST'])
    @login_required
    def reassign_ticket(ticket_id):
        ticket = Ticket.query.get_or_404(ticket_id)
        assignee_id = request.form.get('assignee_id')
        if not assignee_id:
            flash('Nessun membro IT selezionato per la riassegnazione.', 'danger')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        if not current_user.is_manager() and not current_user.is_admin():
            flash('Non hai i permessi per riassegnare questo ticket.', 'danger')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        assignee_id = int(assignee_id)
        assignee = User.query.get(assignee_id)
        if not assignee or assignee.role != UserRole.IT:
            flash('Membro IT selezionato non valido.', 'danger')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        previous_assignee = ticket.assignee.username if ticket.assignee else 'Nessuno'
        ticket.assignee_id = assignee_id
        ticket.status = TicketStatus.ASSIGNED
        db.session.commit()
        # Nota di sistema per la riassegnazione
        reassign_comment = Comment(
            content=f"Ticket riassegnato da {previous_assignee} a {assignee.username} da {current_user.username}",
            ticket_id=ticket.id,
            author_id=current_user.id,
            internal_only=True
        )
        db.session.add(reassign_comment)
        db.session.commit()
        notify_ticket_assigned(ticket)
        flash(f'Ticket riassegnato a {assignee.username}.', 'success')
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))

    @app.route('/uploads/<path:filename>')
    @login_required
    def download_file(filename):
        # Security check: verify that the file exists and belongs to a ticket the user can access
        attachment = Attachment.query.filter_by(file_path=filename).first_or_404()
        ticket = Ticket.query.get(attachment.ticket_id)
        
        # Check permission based on user role
        if (current_user.role == UserRole.USER and ticket.creator_id != current_user.id):
            abort(403)  # Forbidden
        
        if (current_user.role == UserRole.DEPT_MANAGER and 
            ticket.department_id != current_user.managed_department_id):
            abort(403)
        
        if (current_user.role == UserRole.MANAGER and 
            ticket.status not in [TicketStatus.AWAITING_IT_MANAGER_APPROVAL, TicketStatus.APPROVED, 
                                 TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED,
                                 TicketStatus.REJECTED, TicketStatus.CLOSED]):
            abort(403)
        
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

    # Admin routes
    @app.route('/admin/categories')
    @login_required
    def category_list():
        if not current_user.is_admin():
            abort(403)
            
        categories = Category.query.order_by(Category.name).all()
        return render_template('admin/categories.html', categories=categories)

    @app.route('/admin/categories/create', methods=['GET', 'POST'])
    @login_required
    def category_create():
        if not current_user.is_admin():
            abort(403)
            
        form = CategoryForm()
        
        if form.validate_on_submit():
            category = Category(
                name=form.name.data,
                description=form.description.data,
                requires_approval=form.requires_approval.data
            )
            db.session.add(category)
            db.session.commit()
            
            flash('Category created successfully.', 'success')
            return redirect(url_for('category_list'))
            
        return render_template('admin/categories.html', form=form)

    @app.route('/admin/categories/<int:category_id>/edit', methods=['GET', 'POST'])
    @login_required
    def category_edit(category_id):
        if not current_user.is_admin():
            abort(403)
            
        category = Category.query.get_or_404(category_id)
        form = CategoryForm(obj=category)
        form.original_name = form.name
        
        if form.validate_on_submit():
            category.name = form.name.data
            category.description = form.description.data
            category.requires_approval = form.requires_approval.data
            
            db.session.commit()
            flash('Category updated successfully.', 'success')
            return redirect(url_for('category_list'))
            
        return render_template('admin/categories.html', form=form, category=category)

    @app.route('/admin/users')
    @login_required
    def user_list():
        if not current_user.is_admin() and not current_user.is_it():
            abort(403)
            
        users = User.query.order_by(User.username).all()
        form = UserManagementForm()
        
        # Popola le scelte dei dipartimenti
        try:
            departments = Department.query.order_by(Department.name).all()
            form.department_id.choices = [(d.id, d.name) for d in departments]
            form.department_id.choices.insert(0, (0, 'Nessun dipartimento'))
            
            # Popola le scelte per il dipartimento gestito
            form.managed_department_id.choices = [(d.id, d.name) for d in departments]
            form.managed_department_id.choices.insert(0, (0, 'Nessuno')) # Modificato da ('', 'Nessuno')
        except (ImportError, AttributeError):
            # Se Department non esiste o non è accessibile, usa una lista vuota
            form.department_id.choices = [(0, 'Nessun dipartimento')]
            form.managed_department_id.choices = [('', 'Nessuno')]
            
        return render_template('admin/users.html', users=users, form=form, departments=departments if 'departments' in locals() else [])

    @app.route('/admin/users/create', methods=['GET', 'POST'])
    @login_required
    def user_create():
        if not current_user.is_admin() and not current_user.is_it():
            abort(403)
            
        form = UserManagementForm()
        # Popola le scelte dei dipartimenti
        try:
            departments = Department.query.order_by(Department.name).all()
            form.department_id.choices = [(d.id, d.name) for d in departments]
            form.department_id.choices.insert(0, (0, 'Nessun dipartimento'))
            
            # Popola le scelte per il dipartimento gestito
            form.managed_department_id.choices = [(d.id, d.name) for d in departments]
            form.managed_department_id.choices.insert(0, (0, 'Nessuno')) # Modificato da ('', 'Nessuno')
        except (ImportError, AttributeError):
            # Se Department non esiste o non è accessibile, usa una lista vuota
            form.department_id.choices = [(0, 'Nessun dipartimento')]
            form.managed_department_id.choices = [('', 'Nessuno')]
        
        # If IT user is creating, restrict role choices based on requirements
        # IT users can create both USER and MANAGER roles
        if current_user.is_it() and not current_user.is_admin():
            # Restrict to user and manager roles only
            allowed_roles = [UserRole.USER, UserRole.MANAGER]
            form.role.choices = [(role.name, role.value) for role in allowed_roles]
        
        if form.validate_on_submit():
            # Check if IT staff is trying to create an admin (not allowed)
            if current_user.is_it() and not current_user.is_admin() and form.role.data == UserRole.ADMIN.name:
                flash('IT staff cannot create admin users.', 'danger')
                return redirect(url_for('user_list'))
                
            # Gestione del dipartimento gestito
            managed_dept_id = None
            if form.role.data == 'DEPT_MANAGER' and form.managed_department_id.data:
                managed_dept_id = form.managed_department_id.data
                
                # Verifica se il dipartimento ha già un manager
                existing_manager = User.query.filter_by(managed_department_id=managed_dept_id).first()
                if existing_manager:
                    # Rimuovi il manager precedente
                    existing_manager.managed_department_id = None
                    
            user = User(
                username=form.username.data,
                email=form.email.data,
                role=UserRole[form.role.data],
                department_id=form.department_id.data if form.department_id.data and form.department_id.data != 0 else None,
                managed_department_id=managed_dept_id,
                is_active=form.is_active.data
            )
            # Set a default password that user will need to change
            user.set_password('changeme123')
            
            db.session.add(user)
            db.session.commit()
            
            from models import PasswordReset
            pr = PasswordReset(user_id=user.id, must_change=True)
            db.session.add(pr)
            db.session.commit()
            
            flash('User created successfully.', 'success')
            return redirect(url_for('user_list'))
            
        return render_template('admin/users.html', form=form)

    @app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
    @login_required
    def user_edit(user_id):
        if not current_user.is_admin() and not current_user.is_it():
            abort(403)
            
        user = User.query.get_or_404(user_id)
        form = UserManagementForm(obj=user)
        form.original_username = user.username
        form.original_email = user.email
        
        # Set role to string value
        form.role.data = user.role.name
        
        # Popola le scelte dei dipartimenti
        try:
            departments = Department.query.order_by(Department.name).all()
            form.department_id.choices = [(d.id, d.name) for d in departments]
            form.department_id.choices.insert(0, (0, 'Nessun dipartimento'))
            
            # Popola le scelte per il dipartimento gestito
            form.managed_department_id.choices = [(d.id, d.name) for d in departments]
            form.managed_department_id.choices.insert(0, (0, 'Nessuno')) # Modificato da ('', 'Nessuno')
        except (ImportError, AttributeError):
            # Se Department non esiste o non è accessibile, usa una lista vuota
            form.department_id.choices = [(0, 'Nessun dipartimento')]
            form.managed_department_id.choices = [('', 'Nessuno')]
        
        # If IT user is editing, restrict role choices based on requirements
        if current_user.is_it() and not current_user.is_admin():
            # Restrict editing admin users by IT staff
            if user.role == UserRole.ADMIN:
                flash('IT staff cannot edit admin users.', 'danger')
                return redirect(url_for('user_list'))
                
            # Restrict roles to USER and MANAGER only for IT staff
            allowed_roles = [UserRole.USER, UserRole.MANAGER]
            form.role.choices = [(role.name, role.value) for role in allowed_roles]
        
        if form.validate_on_submit():
            # Prevent IT staff from changing role to admin
            if current_user.is_it() and not current_user.is_admin() and form.role.data == UserRole.ADMIN.name:
                flash('IT staff cannot assign admin role.', 'danger')
                return redirect(url_for('user_list'))
            
            # Prevent IT staff from changing role of another IT staff member
            if current_user.is_it() and not current_user.is_admin() and user.role == UserRole.IT and form.role.data != UserRole.IT.name:
                flash('IT staff cannot change the role of other IT staff members.', 'danger')
                return redirect(url_for('user_list'))
                
            # Gestione del dipartimento gestito
            if form.role.data == 'DEPT_MANAGER' and form.managed_department_id.data:
                managed_dept_id = form.managed_department_id.data
                
                # Verifica se il dipartimento ha già un manager diverso da questo utente
                existing_manager = User.query.filter(
                    User.managed_department_id == managed_dept_id,
                    User.id != user.id
                ).first()
                if existing_manager:
                    # Rimuovi il manager precedente
                    existing_manager.managed_department_id = None
                    
                user.managed_department_id = managed_dept_id
            else:
                user.managed_department_id = None
                
            user.username = form.username.data
            user.email = form.email.data
            user.role = UserRole[form.role.data]
            user.department_id = form.department_id.data if form.department_id.data and form.department_id.data != 0 else None
            user.is_active = form.is_active.data
            
            db.session.commit()
            flash('User updated successfully.', 'success')
            return redirect(url_for('user_list'))
            
        return render_template('admin/users.html', form=form, user=user)

    @app.route('/admin/departments')
    @login_required
    def department_list():
        if not current_user.is_admin():
            abort(403)
            
        departments = Department.query.order_by(Department.name).all()
        
        # Ottieni tutti gli utenti che possono essere manager
        available_managers = User.query.filter(
            User.is_active == True
        ).order_by(User.username).all()
        
        return render_template('admin/departments.html', 
                             departments=departments, 
                             available_managers=available_managers)

    @app.route('/admin/departments/create', methods=['GET', 'POST'])
    @login_required
    def department_create():
        if not current_user.is_admin():
            abort(403)
            
        form = DepartmentForm()
        
        if form.validate_on_submit():
            department = Department(
                name=form.name.data,
                description=form.description.data
            )
            db.session.add(department)
            db.session.commit()
            
            flash('Dipartimento creato con successo.', 'success')
            return redirect(url_for('department_list'))
            
        return render_template('admin/department_form.html', form=form, title="Nuovo Dipartimento")

    @app.route('/admin/departments/<int:department_id>/edit', methods=['GET', 'POST'])
    @login_required
    def department_edit(department_id):
        if not current_user.is_admin():
            abort(403)
            
        department = Department.query.get_or_404(department_id)
        form = DepartmentForm(obj=department)
        form.original_name = department.name
        
        if form.validate_on_submit():
            department.name = form.name.data
            department.description = form.description.data
            
            db.session.commit()
            flash('Dipartimento aggiornato con successo.', 'success')
            return redirect(url_for('department_list'))
            
        return render_template('admin/department_form.html', title='Modifica Dipartimento', form=form)


    @app.route('/admin/users/<int:user_id>/reset_password', methods=['POST'])
    @login_required
    def admin_user_reset_password(user_id):
        if not current_user.is_admin():
            abort(403)
            
        user = User.query.get_or_404(user_id)
        form = AdminPasswordResetForm()
        
        if form.validate_on_submit():
            user.set_password(form.password.data)
            # Impone cambio password
            from models import PasswordReset
            pr = PasswordReset.query.filter_by(user_id=user.id).first()
            if pr:
                pr.must_change = True
            else:
                pr = PasswordReset(user_id=user.id, must_change=True)
                db.session.add(pr)
            db.session.commit()
            flash(f'Password aggiornata con successo per l\'utente {user.username}', 'success')
        else:
            for error in form.password.errors:
                flash(f'Errore password: {error}', 'danger')
            for error in form.confirm_password.errors:
                flash(f'Errore conferma password: {error}', 'danger')
                
        return redirect(url_for('user_list'))
    
    @app.route('/admin/departments/assign_manager', methods=['POST'])
    @login_required
    def assign_department_manager():
        if not current_user.is_admin():
            abort(403)
            
        department_id = request.form.get('department_id')
        manager_id = request.form.get('manager_id')
        
        if not department_id or not manager_id:
            flash('Dipartimento e Manager sono obbligatori.', 'danger')
            return redirect(url_for('department_list'))
            
        try:
            department_id = int(department_id)
            manager_id = int(manager_id)
        except (ValueError, TypeError):
            flash('ID dipartimento o manager non valido.', 'danger')
            return redirect(url_for('department_list'))
            
        department = Department.query.get_or_404(department_id)
        manager = User.query.get_or_404(manager_id)
        
        # Rimuovi il manager precedente se esiste
        if department.managed_by:
            old_manager = department.managed_by
            old_manager.managed_department_id = None
            
        # Rimuovi l'utente da qualsiasi altro dipartimento che gestisce
        if manager.managed_department_id:
            manager.managed_department_id = None
            
        # Assegna il nuovo manager
        manager.managed_department_id = department.id
        
        # Promuovi l'utente a DEPT_MANAGER se non lo è già
        if manager.role not in [UserRole.DEPT_MANAGER, UserRole.ADMIN]:
            manager.role = UserRole.DEPT_MANAGER
            
        db.session.commit()
        
        flash(f'Manager {manager.username} assegnato con successo al dipartimento {department.name}.', 'success')
        return redirect(url_for('department_list'))
    
    @app.route('/admin/reports')
    @login_required
    def reports():
        if not (current_user.is_admin() or current_user.is_manager()):
            abort(403)
            
        # Get stats for reporting
        status_counts = get_ticket_status_counts()
        
        # Tickets by category
        from sqlalchemy import func
        category_query = db.session.query(
            Category.name, func.count(Ticket.id)
        ).join(Ticket).group_by(Category.name).all()
        
        # Convertire in liste per renderli JSON serializzabili
        category_stats = [[cat_name, count] for cat_name, count in category_query]
        
        # Tickets by assignee
        assignee_query = db.session.query(
            User.username, func.count(Ticket.id)
        ).join(Ticket, User.id == Ticket.assignee_id).group_by(User.username).all()
        
        # Convertire in liste per renderli JSON serializzabili
        assignee_stats = [[username, count] for username, count in assignee_query]
        
        # Time to resolution stats
        resolved_tickets = Ticket.query.filter(Ticket.status.in_([TicketStatus.RESOLVED, TicketStatus.CLOSED])).all()
        avg_resolution_time = 0
        if resolved_tickets:
            total_hours = 0
            for ticket in resolved_tickets:
                # Simple calculation - just use the difference between created and updated
                diff = ticket.updated_at - ticket.created_at
                total_hours += diff.total_seconds() / 3600
            avg_resolution_time = total_hours / len(resolved_tickets)
        
        return render_template(
            'admin/reports.html',
            status_counts=status_counts,
            category_stats=category_stats,
            assignee_stats=assignee_stats,
            avg_resolution_time=avg_resolution_time
        )
    
    @app.route('/admin/reports/download')
    @login_required
    def download_reports():
        from flask import Response
        if not (current_user.is_admin() or current_user.is_manager()):
            abort(403)
            
        import csv
        import io
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['ID', 'Titolo', 'Categoria', 'Stato', 'Creatore', 'Assegnato a', 'Data Creazione', 'Data Aggiornamento'])
        
        tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()
        for ticket in tickets:
            writer.writerow([
                ticket.id,
                ticket.title,
                ticket.category_rel.name if ticket.category_rel else '',
                ticket.status.value,
                ticket.creator.username if ticket.creator else '',
                ticket.assignee.username if ticket.assignee else '',
                ticket.created_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.created_at else '',
                ticket.updated_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.updated_at else ''
            ])
            
        response = Response(output.getvalue(), mimetype='text/csv')
        response.headers['Content-Disposition'] = f'attachment; filename=tickets_report_{datetime.now().strftime("%Y%m%d")}.csv'
        return response
    
    @app.route('/manager/ticket-history')
    @login_required
    def manager_ticket_history():
        if not current_user.is_manager():
            abort(403)
            
        # Get all statuses and categories for filters
        statuses = [status for status in TicketStatus]
        categories = Category.query.all()
        
        # Base query - manager vede tutti i ticket
        query = Ticket.query
        
        # Apply filters
        status_filter = request.args.get('status')
        if status_filter and status_filter != '':
            query = query.filter(Ticket.status == TicketStatus[status_filter])
        
        category_filter = request.args.get('category')
        if category_filter and category_filter != '':
            query = query.filter(Ticket.category_id == int(category_filter))
        
        # Sort by created date, newest first
        tickets = query.order_by(Ticket.created_at.desc()).all()
        
        return render_template('manager/ticket_history.html', 
                           tickets=tickets, 
                           statuses=statuses, 
                           categories=categories)
    
    # IT routes
    @app.route('/it/assignments')
    @login_required
    def assignments():
        if not current_user.is_it() and not current_user.is_admin():
            abort(403)
        
        # Get unassigned tickets
        unassigned_tickets = Ticket.query.filter_by(status=TicketStatus.APPROVED, assignee_id=None).order_by(Ticket.created_at).all()
        
        # Get tickets assigned to the current user
        my_tickets = Ticket.query.filter_by(assignee_id=current_user.id).filter(
            Ticket.status.in_([TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS, TicketStatus.WAITING_USER])
        ).order_by(Ticket.created_at).all()
        
        # Get IT staff members with their workload
        it_staff = User.query.filter_by(role=UserRole.IT).all()
        workload_data = []
        for staff in it_staff:
            active_tickets = Ticket.query.filter_by(assignee_id=staff.id).filter(
                Ticket.status.notin_([TicketStatus.RESOLVED, TicketStatus.CLOSED, TicketStatus.REJECTED])
            ).count()
            workload_data.append((staff, active_tickets))
        
        return render_template('it/assignments.html', 
                             unassigned_tickets=unassigned_tickets,
                             my_tickets=my_tickets,
                             workload_data=workload_data)
        
    @app.route('/it/dashboard')
    @login_required
    def it_dashboard():
        # Only IT team can access IT dashboard
        if not current_user.is_it() and not current_user.is_admin():
            abort(403)
        
        # Get tickets assigned to the current IT user by status
        assigned_tickets = Ticket.query.filter_by(assignee_id=current_user.id).order_by(Ticket.updated_at.desc()).all()
        
        # Group tickets by status
        tickets_by_status = {
            'assigned': [],
            'in_progress': [],
            'waiting_user': [],
            'resolved': [],
            'closed': [],
            'rejected': []  # Aggiungi categoria per ticket rifiutati
        }
        
        for ticket in assigned_tickets:
            if ticket.status == TicketStatus.ASSIGNED:
                tickets_by_status['assigned'].append(ticket)
            elif ticket.status == TicketStatus.IN_PROGRESS:
                tickets_by_status['in_progress'].append(ticket)
            elif ticket.status == TicketStatus.WAITING_USER:
                tickets_by_status['waiting_user'].append(ticket)
            elif ticket.status == TicketStatus.RESOLVED:
                tickets_by_status['resolved'].append(ticket)
            elif ticket.status == TicketStatus.CLOSED:
                tickets_by_status['closed'].append(ticket)
            elif ticket.status == TicketStatus.REJECTED:
                tickets_by_status['rejected'].append(ticket)
        
        # Ottieni anche i ticket rifiutati per i quali sei stato selezionato come assegnatario
        rejected_tickets = Ticket.query.filter(
            and_(
                Ticket.status == TicketStatus.REJECTED,
                or_(
                    Ticket.assignee_id == current_user.id,
                    and_(
                        Ticket.assignee_id == None,
                        current_user.is_admin()
                    )
                )
            )
        ).all()
        
        # Aggiungi i ticket rifiutati trovati alla lista (senza duplicati)
        for ticket in rejected_tickets:
            if ticket not in tickets_by_status['rejected']:
                tickets_by_status['rejected'].append(ticket)
        
        # Get available tickets that can be assigned
        available_tickets = Ticket.query.filter(
            and_(
                Ticket.assignee_id == None,
                Ticket.status.in_([TicketStatus.NEW, TicketStatus.APPROVED])
            )
        ).order_by(Ticket.created_at.desc()).all()
        
        # Statistics for IT dashboard
        total_assigned = len(assigned_tickets) + len(tickets_by_status['rejected'])
        total_active = len(tickets_by_status['assigned']) + len(tickets_by_status['in_progress']) + len(tickets_by_status['waiting_user'])
        total_closed = len(tickets_by_status['resolved']) + len(tickets_by_status['closed'])
        
        return render_template(
            'it/dashboard.html',
            assigned_tickets=assigned_tickets,
            available_tickets=available_tickets,
            tickets_by_status=tickets_by_status,
            total_assigned=total_assigned,
            total_active=total_active,
            total_closed=total_closed
        )
            
    @app.route('/it/tickets/<int:ticket_id>/update_status', methods=['POST'])
    @login_required
    def it_update_ticket_status(ticket_id):
        # Only IT team can update ticket status
        if not current_user.is_it() and not current_user.is_admin():
            abort(403)
        
        ticket = Ticket.query.get_or_404(ticket_id)
        
        # Check if the current IT user is assigned to this ticket
        if ticket.assignee_id != current_user.id and not current_user.is_admin():
            flash('Puoi aggiornare solo i ticket assegnati a te.', 'danger')
            return redirect(url_for('it_dashboard'))
        
        # Get the new status from the form
        new_status = request.form.get('status')
        notes = request.form.get('notes', '')  # Note opzionali
        
        if not new_status:
            flash('Stato non specificato.', 'danger')
            return redirect(url_for('ticket_detail', ticket_id=ticket_id))
        
        # Validate the status transition
        current_status = ticket.status
        
        valid_transitions = {
            TicketStatus.ASSIGNED: [TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED, TicketStatus.REJECTED, TicketStatus.WAITING_USER],
            TicketStatus.IN_PROGRESS: [TicketStatus.WAITING_USER, TicketStatus.RESOLVED, TicketStatus.CLOSED],
            TicketStatus.WAITING_USER: [TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED]
        }
        
        try:
            new_status_enum = TicketStatus[new_status]
            
            if current_status not in valid_transitions or new_status_enum not in valid_transitions[current_status]:
                flash(f'Transizione di stato non valida da {current_status.value} a {new_status_enum.value}.', 'danger')
                return redirect(url_for('ticket_detail', ticket_id=ticket_id))
            
            # Update the ticket status
            previous_status = ticket.status
            ticket.status = new_status_enum
            ticket.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Messaggi personalizzati per diversi stati
            status_messages = {
                TicketStatus.IN_PROGRESS: f"Ticket in lavorazione da {current_user.username}",
                TicketStatus.WAITING_USER: f"In attesa di feedback dall'utente",
                TicketStatus.RESOLVED: f"Ticket risolto da {current_user.username}",
                TicketStatus.CLOSED: f"Ticket chiuso da {current_user.username}"
            }
            
            status_message = status_messages.get(new_status_enum, f"Stato del ticket cambiato da {previous_status.value} a {new_status_enum.value}")
            
            # Add a system comment about the status change
            comment_content = status_message
            if notes:
                comment_content += f"\n\nNote: {notes}"
                
            comment = Comment(
                content=comment_content,
                ticket_id=ticket_id,
                author_id=current_user.id,
                internal_only=False if new_status == "RESOLVED" or new_status == "CLOSED" else True
            )
            db.session.add(comment)
            db.session.commit()
            
            # Send notification
            notify_ticket_status_change(ticket, previous_status)
            
            # Messaggio personalizzato per l'utente
            user_messages = {
                TicketStatus.IN_PROGRESS: "Il ticket è ora in lavorazione.",
                TicketStatus.WAITING_USER: "Il ticket è ora in attesa di feedback dall'utente.",
                TicketStatus.RESOLVED: "Il ticket è stato risolto. Grazie per la pazienza!",
                TicketStatus.CLOSED: "Il ticket è stato chiuso."
            }
            
            flash_message = user_messages.get(new_status_enum, f'Stato del ticket aggiornato a {new_status_enum.value}.')
            flash(flash_message, 'success')
            
        except (KeyError, ValueError):
            flash('Valore di stato non valido.', 'danger')
        
        return redirect(url_for('ticket_detail', ticket_id=ticket_id))
    
    # Error handlers
    @app.errorhandler(403)
    def forbidden(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(error):
        return render_template('errors/500.html'), 500
