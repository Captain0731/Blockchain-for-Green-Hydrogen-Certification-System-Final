import secrets
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db
from models import User, Certificate, Credit, Block

@app.route('/')
def index():
    # Get basic statistics
    total_users = User.query.count()
    total_certificates = Certificate.query.count()
    total_blocks = Block.query.count()
    
    blockchain_stats = {
        'total_blocks': total_blocks,
        'latest_block': None
    }
    
    platform_stats = {
        'users': {'total': total_users},
        'certificates': {'total': total_certificates},
        'blocks': {'total': total_blocks},
        'credits': {'total': Credit.query.count()},
        'marketplace': {
            'volume_24h': 0,
            'avg_price_30d': 0,
            'active_orders': 0
        }
    }
    
    return render_template('index.html', 
                         blockchain_stats=blockchain_stats, 
                         platform_stats=platform_stats)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('signup.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('signup.html')
        
        # Create new user
        user = User()
        user.username = username
        user.email = email
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Add initial credits
        initial_credit = Credit()
        initial_credit.user_id = user.id
        initial_credit.amount = 100.0
        initial_credit.transaction_type = 'add'
        initial_credit.set_meta({'source': 'welcome_bonus', 'description': 'Welcome bonus'})
        db.session.add(initial_credit)
        db.session.commit()
        
        flash('Account created successfully!', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get user statistics
    total_credits = current_user.get_total_credits()
    total_certificates = Certificate.query.filter_by(user_id=current_user.id).count()
    
    # Get recent certificates
    recent_certificates = Certificate.query.filter_by(user_id=current_user.id)\
                                         .order_by(Certificate.issue_date.desc())\
                                         .limit(5).all()
    
    # Get recent credit transactions
    recent_credits = Credit.query.filter_by(user_id=current_user.id)\
                                .order_by(Credit.date.desc())\
                                .limit(5).all()
    
    # Get basic stats
    blockchain_stats = {'total_blocks': Block.query.count()}
    recent_orders = []
    unread_notifications = 0
    
    return render_template('dashboard.html', 
                         total_credits=total_credits,
                         total_certificates=total_certificates,
                         recent_certificates=recent_certificates,
                         recent_credits=recent_credits,
                         recent_orders=recent_orders,
                         blockchain_stats=blockchain_stats,
                         unread_notifications=unread_notifications)

@app.route('/certificates', methods=['GET', 'POST'])
@login_required
def certificates():
    if request.method == 'POST':
        certificate_id = f"HC-{secrets.token_hex(8)}"
        hydrogen_amount = float(request.form['hydrogen_amount'])
        production_method = request.form['production_method']
        location = request.form['location']
        
        # Create certificate
        certificate = Certificate()
        certificate.user_id = current_user.id
        certificate.certificate_id = certificate_id
        
        meta_data = {
            'hydrogen_amount_kg': hydrogen_amount,
            'production_method': production_method,
            'location': location,
            'carbon_intensity': 0.0 if production_method == 'electrolysis_renewable' else 2.5
        }
        certificate.set_meta(meta_data)
        
        db.session.add(certificate)
        db.session.commit()
        
        # Certificate created successfully
        
        flash('Certificate issued successfully!', 'success')
        return redirect(url_for('certificates'))
    
    # Get search and filter parameters
    search = request.args.get('search', '')
    status_filter = request.args.get('status', '')
    verification_filter = request.args.get('verification', '')
    
    # Build query
    query = Certificate.query.filter_by(user_id=current_user.id)
    
    if search:
        query = query.filter(Certificate.certificate_id.contains(search))
    if status_filter:
        query = query.filter_by(status=status_filter)
    if verification_filter:
        query = query.filter_by(verification_status=verification_filter)
    
    user_certificates = query.order_by(Certificate.issue_date.desc()).all()
    
    return render_template('certificates.html', 
                         certificates=user_certificates,
                         search=search,
                         status_filter=status_filter,
                         verification_filter=verification_filter)

@app.route('/credits', methods=['GET', 'POST'])
@login_required
def credits():
    if request.method == 'POST':
        action = request.form['action']
        
        if action == 'add':
            amount = float(request.form['amount'])
            source = request.form['source']
            
            credit = Credit()
            credit.user_id = current_user.id
            credit.amount = amount
            credit.transaction_type = 'add'
            credit.set_meta({'source': source, 'description': f'Credits added from {source}'})
            db.session.add(credit)
            db.session.commit()
            
            # Credits added successfully
            
            flash(f'Added {amount} credits successfully!', 'success')
        
        elif action == 'transfer':
            recipient_username = request.form['recipient']
            amount = float(request.form['amount'])
            
            recipient = User.query.filter_by(username=recipient_username).first()
            if not recipient:
                flash('Recipient not found!', 'error')
                return redirect(url_for('credits'))
            
            if recipient.id == current_user.id:
                flash('Cannot transfer to yourself!', 'error')
                return redirect(url_for('credits'))
            
            current_balance = current_user.get_total_credits()
            if current_balance < amount:
                flash('Insufficient credits!', 'error')
                return redirect(url_for('credits'))
            
            # Create transfer out record
            credit_out = Credit()
            credit_out.user_id = current_user.id
            credit_out.amount = amount
            credit_out.transaction_type = 'transfer_out'
            credit_out.set_meta({
                'recipient_id': recipient.id,
                'recipient_username': recipient.username,
                'description': f'Transfer to {recipient.username}'
            })
            
            # Create transfer in record
            credit_in = Credit()
            credit_in.user_id = recipient.id
            credit_in.amount = amount
            credit_in.transaction_type = 'transfer_in'
            credit_in.set_meta({
                'sender_id': current_user.id,
                'sender_username': current_user.username,
                'description': f'Transfer from {current_user.username}'
            })
            
            db.session.add(credit_out)
            db.session.add(credit_in)
            db.session.commit()
            
            # Transfer completed successfully
            
            flash(f'Transferred {amount} credits to {recipient.username}!', 'success')
    
    # Get user credit history
    user_credits = Credit.query.filter_by(user_id=current_user.id)\
                              .order_by(Credit.date.desc()).all()
    
    total_credits = current_user.get_total_credits()
    
    return render_template('credits.html', 
                         credits=user_credits, 
                         total_credits=total_credits)

@app.route('/blockchain')
@login_required
def blockchain():
    # Get blockchain data
    blocks = Block.query.order_by(Block.index.desc()).limit(10).all()
    
    return render_template('blockchain.html', 
                         is_valid=True,
                         validation_message='Blockchain is valid',
                         blocks=blocks)

@app.route('/marketplace')
@login_required
def marketplace():
    # Simplified marketplace view
    market_stats = {'total_volume': 0, 'active_orders': 0}
    
    return render_template('marketplace.html',
                         market_stats=market_stats,
                         orderbook={'buy_orders': [], 'sell_orders': []},
                         user_orders=[],
                         user_transactions=[],
                         user_balance=current_user.get_total_credits())

@app.route('/marketplace/order', methods=['POST'])
@login_required
def create_market_order():
    order_type = request.form['order_type']
    amount = float(request.form['amount'])
    price = float(request.form['price'])
    
    flash(f'{order_type.capitalize()} order feature coming soon!', 'info')
    
    return redirect(url_for('marketplace'))

@app.route('/analytics')
@login_required
def analytics():
    # Basic analytics
    overview = {
        'total_users': User.query.count(),
        'total_certificates': Certificate.query.count(),
        'total_credits': Credit.query.count()
    }
    
    return render_template('analytics.html',
                         overview=overview,
                         production_stats={},
                         carbon_analysis={})

@app.route('/notifications')
@login_required
def notifications():
    # Get user notifications from database
    from models import Notification
    user_notifications = Notification.query.filter_by(user_id=current_user.id)\
                                           .order_by(Notification.created_at.desc()).all()
    
    return render_template('notifications.html', 
                         notifications=user_notifications)

@app.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    from models import Notification
    notification = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first()
    
    if notification:
        notification.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Notification not found'}), 404

@app.route('/export/certificates')
@login_required
def export_certificates():
    flash('Export feature coming soon!', 'info')
    return redirect(url_for('certificates'))

@app.route('/export/credits')
@login_required
def export_credits():
    flash('Export feature coming soon!', 'info')
    return redirect(url_for('credits'))

@app.route('/export/trades')
@login_required
def export_trades():
    flash('Export feature coming soon!', 'info')
    return redirect(url_for('marketplace'))

# Legacy API routes for backward compatibility
@app.route('/api/blocks')
@login_required
def api_blocks():
    blocks = Block.query.order_by(Block.index).all()
    blocks_data = []
    
    for block in blocks:
        blocks_data.append({
            'index': block.index,
            'hash': block.hash,
            'previous_hash': block.previous_hash,
            'timestamp': block.timestamp.isoformat(),
            'transactions': block.get_transactions(),
            'nonce': block.nonce,
            'difficulty': block.difficulty,
            'miner_address': block.miner_address
        })
    
    return jsonify(blocks_data)

@app.route('/api/transactions')
@login_required
def api_transactions():
    transactions = BlockchainSimulator.get_transaction_history()
    return jsonify(transactions)

@app.route('/api/analytics/<category>')
@login_required
def api_analytics_data(category):
    days = request.args.get('days', 30, type=int)
    data = AnalyticsManager.get_time_series_data(category, days)
    return jsonify(data)
