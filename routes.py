import secrets
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db
from models import User, Certificate, Credit, Block, Notification
from blockchain import BlockchainSimulator
from analytics import AnalyticsManager
from marketplace import CarbonCreditMarketplace

@app.route('/')
def index():
    # Get basic statistics
    overview = AnalyticsManager.get_platform_overview()
    blockchain_stats = BlockchainSimulator.get_blockchain_stats()
    
    return render_template('index.html', 
                          blockchain_stats=blockchain_stats, 
                          platform_stats=overview)

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
    # Get user analytics
    user_analytics = AnalyticsManager.get_user_analytics(current_user.id)
    
    # Get recent certificates
    recent_certificates = Certificate.query.filter_by(user_id=current_user.id)\
                                          .order_by(Certificate.issue_date.desc())\
                                          .limit(5).all()
    
    # Get recent credit transactions
    recent_credits = Credit.query.filter_by(user_id=current_user.id)\
                                .order_by(Credit.date.desc())\
                                .limit(5).all()
    
    # Get recent orders and transactions
    recent_orders = CarbonCreditMarketplace.get_user_orders(current_user.id)[:5]
    recent_transactions = CarbonCreditMarketplace.get_user_transactions(current_user.id)[:5]
    
    # Get blockchain stats
    blockchain_stats = BlockchainSimulator.get_blockchain_stats()
    
    # Get unread notifications count
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return render_template('dashboard.html', 
                          user_analytics=user_analytics,
                          recent_certificates=recent_certificates,
                          recent_credits=recent_credits,
                          recent_orders=recent_orders,
                          recent_transactions=recent_transactions,
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
        
        # Add to blockchain
        blockchain_transaction = {
            'type': 'certificate_issued',
            'certificate_id': certificate_id,
            'user_id': current_user.id,
            'hydrogen_amount': hydrogen_amount,
            'production_method': production_method,
            'timestamp': datetime.utcnow().isoformat()
        }
        BlockchainSimulator.add_block([blockchain_transaction])
        
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
            
            # Add to blockchain
            blockchain_transaction = {
                'type': 'credits_added',
                'user_id': current_user.id,
                'amount': amount,
                'source': source,
                'timestamp': datetime.utcnow().isoformat()
            }
            BlockchainSimulator.add_block([blockchain_transaction])
            
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
            
            # Add to blockchain
            blockchain_transaction = {
                'type': 'credit_transfer',
                'from_user_id': current_user.id,
                'to_user_id': recipient.id,
                'amount': amount,
                'timestamp': datetime.utcnow().isoformat()
            }
            BlockchainSimulator.add_block([blockchain_transaction])
            
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
    blockchain_stats = BlockchainSimulator.get_blockchain_stats()
    
    return render_template('blockchain.html', 
                          is_valid=blockchain_stats['is_valid'],
                          validation_message='Blockchain is valid' if blockchain_stats['is_valid'] else 'Blockchain validation failed',
                          blocks=blocks,
                          blockchain_stats=blockchain_stats)

@app.route('/marketplace', methods=['GET', 'POST'])
@login_required
def marketplace():
    if request.method == 'POST':
        order_type = request.form['order_type']
        amount = float(request.form['amount'])
        price = float(request.form['price'])
        
        success, message = CarbonCreditMarketplace.create_order(
            current_user.id, order_type, amount, price
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('marketplace'))
    
    # Get market data
    market_stats = CarbonCreditMarketplace.get_market_stats()
    orderbook = CarbonCreditMarketplace.get_order_book()
    user_orders = CarbonCreditMarketplace.get_user_orders(current_user.id)
    user_transactions = CarbonCreditMarketplace.get_user_transactions(current_user.id)
    
    return render_template('marketplace.html',
                          market_stats=market_stats,
                          orderbook=orderbook,
                          user_orders=user_orders,
                          user_transactions=user_transactions,
                          user_balance=current_user.get_total_credits())

@app.route('/marketplace/cancel/<int:order_id>')
@login_required
def cancel_order(order_id):
    success, message = CarbonCreditMarketplace.cancel_order(order_id, current_user.id)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('marketplace'))

@app.route('/analytics')
@login_required
def analytics():
    overview = AnalyticsManager.get_platform_overview()
    production_stats = AnalyticsManager.get_production_statistics()
    carbon_analysis = AnalyticsManager.get_carbon_analysis()
    market_analysis = AnalyticsManager.get_market_analysis()
    
    return render_template('analytics.html',
                          overview=overview,
                          production_stats=production_stats,
                          carbon_analysis=carbon_analysis,
                          market_analysis=market_analysis)

@app.route('/notifications')
@login_required
def notifications():
    user_notifications = Notification.query.filter_by(user_id=current_user.id)\
                                           .order_by(Notification.created_at.desc()).all()
    
    return render_template('notifications.html', 
                          notifications=user_notifications)

@app.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
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

# API routes for backward compatibility
@app.route('/api/blocks')
@login_required
def api_blocks():
    blocks = Block.query.order_by(Block.index).all()
    blocks_data = []
    
    for block in blocks:
        blocks_data.append({
            'index': block.index,
            'hash': block.hash,
            'timestamp': block.timestamp.isoformat(),
            'previous_hash': block.previous_hash,
            'transactions': block.get_transactions(),
            'nonce': block.nonce,
            'difficulty': block.difficulty
        })
    
    return jsonify(blocks_data)

@app.route('/api/stats')
@login_required
def api_stats():
    overview = AnalyticsManager.get_platform_overview()
    blockchain_stats = BlockchainSimulator.get_blockchain_stats()
    market_stats = CarbonCreditMarketplace.get_market_stats()
    
    return jsonify({
        'platform': overview,
        'blockchain': blockchain_stats,
        'marketplace': market_stats
    })
