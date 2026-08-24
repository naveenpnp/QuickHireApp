from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from models import MessageModel, JobModel, UserModel, db_cursor
from services.auth_service import login_required, get_current_user

message_bp = Blueprint('message_routes', __name__)

@message_bp.route('/messages')
@login_required
def inbox():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    messages = MessageModel.get_user_inbox(user['id'])
    return render_template('messages.html', messages=messages, user=user)

@message_bp.route('/messages/<int:job_id>/<int:recipient_id>', methods=['GET', 'POST'])
@login_required
def conversation(job_id, recipient_id):
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    job = JobModel.get_by_id(job_id)
    if not job:
        flash("Job not found.", "danger")
        return redirect(url_for('job_routes.jobs'))

    recipient = UserModel.get_by_id(recipient_id)
    if not recipient:
        flash("Recipient not found.", "danger")
        return redirect(url_for('job_routes.job_details', job_id=job_id))

    if request.method == 'POST':
        msg_text = request.form.get('message', '').strip()
        if not msg_text:
            flash("Message cannot be empty.", "warning")
        else:
            MessageModel.create(job_id, user['id'], recipient_id, msg_text)
            flash("Message sent successfully!", "success")
        return redirect(url_for('message_routes.conversation', job_id=job_id, recipient_id=recipient_id))

    chat_history = MessageModel.get_conversation(job_id, user['id'], recipient_id)
    return render_template(
        'conversation.html',
        job=job,
        recipient=recipient,
        user=user,
        chat_history=chat_history
    )
