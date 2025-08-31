from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from app import socketio
from models import User
from blockchain import BlockchainSimulator
from marketplace import CarbonCreditMarketplace
from analytics import AnalyticsManager

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    if current_user.is_authenticated:
        # Join user-specific room for personalized notifications
        join_room(f'user_{current_user.id}')
        
        # Send initial data
        emit('connected', {
            'user_id': current_user.id,
            'username': current_user.username,
            'timestamp': str(current_user.created_at)
        })
        
        print(f"User {current_user.username} connected to WebSocket")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if current_user.is_authenticated:
        leave_room(f'user_{current_user.id}')
        print(f"User {current_user.username} disconnected from WebSocket")

@socketio.on('join_blockchain_room')
def handle_join_blockchain():
    """Join blockchain updates room"""
    if current_user.is_authenticated:
        join_room('blockchain_updates')
        
        # Send current blockchain stats
        stats = BlockchainSimulator.get_blockchain_stats()
        if stats['latest_block']:
            latest_block = stats['latest_block']
            stats['latest_block'] = {
                'index': latest_block.index,
                'hash': latest_block.hash,
                'timestamp': latest_block.timestamp.isoformat(),
                'transaction_count': len(latest_block.get_transactions())
            }
        
        emit('blockchain_stats', stats)

@socketio.on('join_marketplace_room')
def handle_join_marketplace():
    """Join marketplace updates room"""
    if current_user.is_authenticated:
        join_room('marketplace_updates')
        
        # Send current market stats
        stats = CarbonCreditMarketplace.get_market_stats()
        emit('market_stats', stats)
        
        # Send current order book
        orderbook = CarbonCreditMarketplace.get_order_book()
        emit('orderbook_update', orderbook)

@socketio.on('request_live_data')
def handle_live_data_request(data):
    """Handle requests for live data updates"""
    if not current_user.is_authenticated:
        return
    
    data_type = data.get('type')
    
    if data_type == 'blockchain':
        stats = BlockchainSimulator.get_blockchain_stats()
        if stats['latest_block']:
            latest_block = stats['latest_block']
            stats['latest_block'] = {
                'index': latest_block.index,
                'hash': latest_block.hash,
                'timestamp': latest_block.timestamp.isoformat(),
                'transaction_count': len(latest_block.get_transactions())
            }
        emit('live_blockchain_data', stats)
    
    elif data_type == 'marketplace':
        market_stats = CarbonCreditMarketplace.get_market_stats()
        orderbook = CarbonCreditMarketplace.get_order_book()
        
        emit('live_marketplace_data', {
            'stats': market_stats,
            'orderbook': orderbook
        })
    
    elif data_type == 'analytics':
        overview = AnalyticsManager.get_platform_overview()
        emit('live_analytics_data', overview)
    
    elif data_type == 'user_stats':
        user_stats = {
            'total_credits': current_user.get_total_credits(),
            'certificate_count': len(current_user.certificates),
            'trade_count': len(current_user.trade_orders)
        }
        emit('live_user_stats', user_stats)

@socketio.on('subscribe_to_notifications')
def handle_notification_subscription():
    """Subscribe to real-time notifications"""
    if current_user.is_authenticated:
        from notifications import NotificationManager
        
        # Get unread notifications count
        unread_count = NotificationManager.get_unread_count(current_user.id)
        
        emit('notification_subscription_confirmed', {
            'unread_count': unread_count
        })

@socketio.on('request_blockchain_visualization')
def handle_blockchain_visualization():
    """Send blockchain data for 3D visualization"""
    if not current_user.is_authenticated:
        return
    
    from models import Block
    
    # Get recent blocks for visualization
    recent_blocks = Block.query.order_by(Block.index.desc()).limit(20).all()
    
    visualization_data = {
        'blocks': [],
        'connections': []
    }
    
    for i, block in enumerate(reversed(recent_blocks)):
        block_data = {
            'index': block.index,
            'hash': block.hash,
            'timestamp': block.timestamp.isoformat(),
            'transaction_count': len(block.get_transactions()),
            'difficulty': block.difficulty,
            'position': {'x': i * 2, 'y': 0, 'z': 0}  # Simple linear layout
        }
        visualization_data['blocks'].append(block_data)
        
        # Add connection to previous block
        if i > 0:
            visualization_data['connections'].append({
                'from': block.previous_hash,
                'to': block.hash
            })
    
    emit('blockchain_visualization_data', visualization_data)

@socketio.on('simulate_mining')
def handle_mining_simulation():
    """Simulate blockchain mining for demonstration"""
    if not current_user.is_authenticated:
        return
    
    # Create a demo transaction
    demo_transactions = [{
        'type': 'demo_transaction',
        'user_id': current_user.id,
        'message': 'Demo mining simulation',
        'timestamp': BlockchainSimulator.calculate_hash(0, "0", str(current_user.id), [], 0)[:16]
    }]
    
    # Mine the block (this will emit real-time updates automatically)
    new_block = BlockchainSimulator.add_block(demo_transactions, f'user_{current_user.id}')
    
    emit('mining_complete', {
        'block_index': new_block.index,
        'block_hash': new_block.hash,
        'message': 'Demo block mined successfully!'
    })

@socketio.on('ping')
def handle_ping():
    """Handle ping for connection testing"""
    emit('pong', {'timestamp': str(current_user.created_at) if current_user.is_authenticated else 'anonymous'})

# Error handling for WebSocket events
@socketio.on_error_default
def default_error_handler(e):
    """Handle WebSocket errors"""
    print(f"WebSocket error: {str(e)}")
    if current_user.is_authenticated:
        emit('error', {'message': 'An error occurred', 'details': str(e)})
