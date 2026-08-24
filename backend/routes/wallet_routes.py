from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import TransactionModel, UserModel, db_cursor
from services.auth_service import login_required, get_current_user

wallet_bp = Blueprint('wallet_routes', __name__)

@wallet_bp.route('/wallet')
@login_required
def wallet():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    transactions = TransactionModel.get_by_user(user['id'])
    total_balance = round(user['wallet_balance'] + user['secured_balance'], 2)

    return render_template(
        'wallet.html',
        user=user,
        transactions=transactions,
        total_balance=total_balance
    )

@wallet_bp.route('/wallet/topup', methods=['POST'])
@login_required
def topup():
    user = get_current_user()
    if not user:
        return redirect(url_for('auth_routes.login'))

    try:
        amount = float(request.form.get('amount', '0'))
        if amount <= 0:
            raise ValueError("Amount must be greater than 0.")
    except ValueError:
        flash("Please enter a valid top-up amount.", "danger")
        return redirect(url_for('wallet_routes.wallet'))

    with db_cursor(commit=True) as cur:
        cur.execute("SELECT wallet_balance FROM users WHERE id = ?", (user['id'],))
        current_wallet = cur.fetchone()['wallet_balance']
        new_wallet = round(current_wallet + amount, 2)
        cur.execute("UPDATE users SET wallet_balance = ? WHERE id = ?", (new_wallet, user['id']))

        cur.execute("""
            INSERT INTO transactions (user_id, amount, transaction_type, description)
            VALUES (?, ?, 'Credit', ?)
        """, (user['id'], amount, f"Wallet Deposit (+₹{amount:,.2f})"))

    flash(f"Successfully deposited ₹{amount:,.2f} into your QuickHire wallet!", "success")
    return redirect(url_for('wallet_routes.wallet'))
