from flask import jsonify, request
from flask_login import login_required, current_user
from app import app
from models import Certificate, Credit, Block, TradeOrder, MarketTransaction, Notification
from blockchain import BlockchainSimulator
from marketplace import CarbonCreditMarketplace
from analytics import AnalyticsManager
from smart_contracts import SmartContractManager
from notifications import NotificationManager

# API Routes for external integrations

@app.route('/api/v1/certificates', methods=['GET'])
@login_required
def api_get_certificates():
    """Get user's certificates"""
    certificates = Certificate.query.filter_by(user_id=current_user.id).all()
    
    return jsonify({
        'certificates': [{
            'id': cert.id,
            'certificate_id': cert.certificate_id,
            'issue_date': cert.issue_date.isoformat(),
            'status': cert.status,
            'verification_status': cert.verification_status,
            'meta': cert.get_meta()
        } for cert in certificates]
    })

@app.route('/api/v1/certificates/<certificate_id>', methods=['GET'])
@login_required
def api_get_certificate(certificate_id):
    """Get specific certificate details"""
    certificate = Certificate.query.filter_by(
        certificate_id=certificate_id,
        user_id=current_user.id
    ).first()
    
    if not certificate:
        return jsonify({'error': 'Certificate not found'}), 404
    
    return jsonify({
        'id': certificate.id,
        'certificate_id': certificate.certificate_id,
        'issue_date': certificate.issue_date.isoformat(),
        'status': certificate.status,
        'verification_status': certificate.verification_status,
        'smart_contract_address': certificate.smart_contract_address,
        'meta': certificate.get_meta()
    })

@app.route('/api/v1/credits/balance', methods=['GET'])
@login_required
def api_get_credit_balance():
    """Get user's credit balance"""
    balance = current_user.get_total_credits()
    
    return jsonify({
        'user_id': current_user.id,
        'balance': balance,
        'username': current_user.username
    })

@app.route('/api/v1/credits/history', methods=['GET'])
@login_required
def api_get_credit_history():
    """Get user's credit transaction history"""
    limit = request.args.get('limit', 50, type=int)
    
    credits = Credit.query.filter_by(user_id=current_user.id)\
                         .order_by(Credit.date.desc())\
                         .limit(limit).all()
    
    return jsonify({
        'transactions': [{
            'id': credit.id,
            'amount': credit.amount,
            'transaction_type': credit.transaction_type,
            'date': credit.date.isoformat(),
            'meta': credit.get_meta()
        } for credit in credits]
    })

@app.route('/api/v1/blockchain/stats', methods=['GET'])
@login_required
def api_blockchain_stats():
    """Get blockchain statistics"""
    stats = BlockchainSimulator.get_blockchain_stats()
    
    # Convert latest_block to dict if it exists
    if stats['latest_block']:
        latest_block = stats['latest_block']
        stats['latest_block'] = {
            'index': latest_block.index,
            'hash': latest_block.hash,
            'timestamp': latest_block.timestamp.isoformat(),
            'transaction_count': len(latest_block.get_transactions())
        }
    
    return jsonify(stats)

@app.route('/api/v1/blockchain/blocks', methods=['GET'])
@login_required
def api_blockchain_blocks():
    """Get blockchain blocks with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    blocks = Block.query.order_by(Block.index.desc())\
                       .paginate(page=page, per_page=per_page, error_out=False)
    
    return jsonify({
        'blocks': [{
            'index': block.index,
            'hash': block.hash,
            'previous_hash': block.previous_hash,
            'timestamp': block.timestamp.isoformat(),
            'transactions': block.get_transactions(),
            'nonce': block.nonce,
            'difficulty': block.difficulty,
            'miner_address': block.miner_address
        } for block in blocks.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': blocks.total,
            'pages': blocks.pages
        }
    })

@app.route('/api/v1/marketplace/stats', methods=['GET'])
@login_required
def api_marketplace_stats():
    """Get marketplace statistics"""
    stats = CarbonCreditMarketplace.get_market_stats()
    return jsonify(stats)

@app.route('/api/v1/marketplace/orderbook', methods=['GET'])
@login_required
def api_marketplace_orderbook():
    """Get current order book"""
    limit = request.args.get('limit', 10, type=int)
    orderbook = CarbonCreditMarketplace.get_order_book(limit)
    return jsonify(orderbook)

@app.route('/api/v1/marketplace/orders', methods=['GET', 'POST'])
@login_required
def api_marketplace_orders():
    """Get user orders or create new order"""
    if request.method == 'GET':
        status = request.args.get('status')
        orders = CarbonCreditMarketplace.get_user_orders(current_user.id, status)
        
        return jsonify({
            'orders': [{
                'id': order.id,
                'order_type': order.order_type,
                'amount': order.amount,
                'price_per_credit': order.price_per_credit,
                'status': order.status,
                'created_at': order.created_at.isoformat(),
                'completed_at': order.completed_at.isoformat() if order.completed_at else None
            } for order in orders]
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        required_fields = ['order_type', 'amount', 'price_per_credit']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing field: {field}'}), 400
        
        success, result = CarbonCreditMarketplace.create_order(
            current_user.id,
            data['order_type'],
            float(data['amount']),
            float(data['price_per_credit']),
            data.get('meta_data')
        )
        
        if success:
            return jsonify({
                'id': result.id,
                'order_type': result.order_type,
                'amount': result.amount,
                'price_per_credit': result.price_per_credit,
                'status': result.status,
                'created_at': result.created_at.isoformat()
            }), 201
        else:
            return jsonify({'error': result}), 400

@app.route('/api/v1/marketplace/orders/<int:order_id>', methods=['DELETE'])
@login_required
def api_cancel_order(order_id):
    """Cancel a trade order"""
    success, message = CarbonCreditMarketplace.cancel_order(order_id, current_user.id)
    
    if success:
        return jsonify({'message': message})
    else:
        return jsonify({'error': message}), 400

@app.route('/api/v1/analytics/overview', methods=['GET'])
@login_required
def api_analytics_overview():
    """Get platform analytics overview"""
    overview = AnalyticsManager.get_platform_overview()
    return jsonify(overview)

@app.route('/api/v1/analytics/timeseries/<category>', methods=['GET'])
@login_required
def api_analytics_timeseries(category):
    """Get time series analytics data"""
    days = request.args.get('days', 30, type=int)
    
    valid_categories = ['users', 'certificates', 'credits', 'blockchain', 'marketplace']
    if category not in valid_categories:
        return jsonify({'error': 'Invalid category'}), 400
    
    data = AnalyticsManager.get_time_series_data(category, days)
    return jsonify(data)

@app.route('/api/v1/smart-contracts', methods=['GET'])
@login_required
def api_smart_contracts():
    """Get smart contract statistics"""
    stats = SmartContractManager.get_contract_stats()
    return jsonify(stats)

@app.route('/api/v1/smart-contracts/execute', methods=['POST'])
@login_required
def api_execute_smart_contract():
    """Execute a smart contract function"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    required_fields = ['contract_address', 'function_name', 'parameters']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing field: {field}'}), 400
    
    success, result = SmartContractManager.execute_contract(
        data['contract_address'],
        data['function_name'],
        data['parameters'],
        f'user_{current_user.id}'
    )
    
    if success:
        return jsonify({'result': result})
    else:
        return jsonify({'error': result}), 400

@app.route('/api/v1/notifications', methods=['GET'])
@login_required
def api_get_notifications():
    """Get user notifications"""
    limit = request.args.get('limit', 50, type=int)
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    
    notifications = NotificationManager.get_user_notifications(
        current_user.id, 
        limit, 
        unread_only
    )
    
    return jsonify({
        'notifications': [{
            'id': notif.id,
            'title': notif.title,
            'message': notif.message,
            'type': notif.notification_type,
            'is_read': notif.is_read,
            'created_at': notif.created_at.isoformat(),
            'meta': notif.get_meta()
        } for notif in notifications],
        'unread_count': NotificationManager.get_unread_count(current_user.id)
    })

@app.route('/api/v1/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def api_mark_notification_read(notification_id):
    """Mark notification as read"""
    success = NotificationManager.mark_as_read(notification_id, current_user.id)
    
    if success:
        return jsonify({'message': 'Notification marked as read'})
    else:
        return jsonify({'error': 'Notification not found'}), 404

@app.route('/api/v1/notifications/read-all', methods=['POST'])
@login_required
def api_mark_all_notifications_read():
    """Mark all notifications as read"""
    count = NotificationManager.mark_all_as_read(current_user.id)
    return jsonify({'message': f'Marked {count} notifications as read'})

# Error handlers for API
@app.errorhandler(404)
def api_not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found'}), 404
    return error

@app.errorhandler(500)
def api_internal_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return error
