from datetime import datetime
from sqlalchemy import and_, or_
from app import db
from models import TradeOrder, TradeTransaction, User, Credit

class CarbonCreditMarketplace:
    """Carbon credit trading marketplace"""
    
    @staticmethod
    def create_order(user_id, order_type, amount, price_per_credit):
        """Create a new trading order"""
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
        
        # Validate order type
        if order_type not in ['buy', 'sell']:
            return False, "Invalid order type"
        
        # Validate sell order - user must have enough credits
        if order_type == 'sell':
            user_balance = user.get_total_credits()
            if user_balance < amount:
                return False, f"Insufficient credits. Available: {user_balance}, Required: {amount}"
        
        # Create the order
        order = TradeOrder()
        order.user_id = user_id
        order.order_type = order_type
        order.amount = amount
        order.price_per_credit = price_per_credit
        
        db.session.add(order)
        db.session.commit()
        
        # Try to match with existing orders
        CarbonCreditMarketplace._try_match_orders()
        
        # Emit market update
        try:
            from app import socketio
            socketio.emit('new_order', {
                'order_id': order.id,
                'type': order_type,
                'amount': amount,
                'price': price_per_credit,
                'user_id': user_id
            }, to='marketplace_updates')
        except Exception as e:
            print(f"Could not emit market update: {e}")
        
        return True, f"{order_type.capitalize()} order created successfully"
    
    @staticmethod
    def cancel_order(order_id, user_id):
        """Cancel a trading order"""
        order = TradeOrder.query.filter_by(
            id=order_id, 
            user_id=user_id, 
            status='active'
        ).first()
        
        if not order:
            return False, "Order not found or already processed"
        
        order.status = 'cancelled'
        db.session.commit()
        
        return True, "Order cancelled successfully"
    
    @staticmethod
    def _try_match_orders():
        """Attempt to match buy and sell orders"""
        # Get active buy orders sorted by price (highest first)
        buy_orders = TradeOrder.query.filter_by(
            order_type='buy', 
            status='active'
        ).order_by(TradeOrder.price_per_credit.desc()).all()
        
        # Get active sell orders sorted by price (lowest first)
        sell_orders = TradeOrder.query.filter_by(
            order_type='sell', 
            status='active'
        ).order_by(TradeOrder.price_per_credit.asc()).all()
        
        for buy_order in buy_orders:
            for sell_order in sell_orders:
                # Check if prices match (buyer willing to pay >= seller asking price)
                if buy_order.price_per_credit >= sell_order.price_per_credit:
                    # Execute the trade
                    CarbonCreditMarketplace._execute_trade(buy_order, sell_order)
                    break  # Move to next buy order after a match
    
    @staticmethod
    def _execute_trade(buy_order, sell_order):
        """Execute a trade between matching orders"""
        # Determine trade amount (minimum of both orders)
        trade_amount = min(buy_order.amount, sell_order.amount)
        
        # Use the sell order price (market maker gets better price)
        trade_price = sell_order.price_per_credit
        total_price = trade_amount * trade_price
        
        # Create trade transaction
        transaction = TradeTransaction()
        transaction.buyer_id = buy_order.user_id
        transaction.seller_id = sell_order.user_id
        transaction.amount = trade_amount
        transaction.price_per_credit = trade_price
        transaction.total_price = total_price
        
        db.session.add(transaction)
        
        # Update orders
        buy_order.amount -= trade_amount
        sell_order.amount -= trade_amount
        
        # Mark orders as filled if completely executed
        if buy_order.amount == 0:
            buy_order.status = 'filled'
            buy_order.filled_at = datetime.utcnow()
        
        if sell_order.amount == 0:
            sell_order.status = 'filled'
            sell_order.filled_at = datetime.utcnow()
        
        # Update user credits
        # Seller loses credits
        seller_credit = Credit()
        seller_credit.user_id = sell_order.user_id
        seller_credit.amount = trade_amount
        seller_credit.transaction_type = 'trade'
        seller_credit.meta_data = f'{{"trade_id": {transaction.id}, "role": "seller", "price_per_credit": {trade_price}}}'
        
        # Buyer gains credits
        buyer_credit = Credit()
        buyer_credit.user_id = buy_order.user_id
        buyer_credit.amount = trade_amount
        buyer_credit.transaction_type = 'add'
        buyer_credit.meta_data = f'{{"trade_id": {transaction.id}, "role": "buyer", "price_per_credit": {trade_price}}}'
        
        db.session.add(seller_credit)
        db.session.add(buyer_credit)
        db.session.commit()
        
        # Send notifications
        try:
            from notifications import NotificationManager
            NotificationManager.send_trade_notification(transaction)
        except Exception as e:
            print(f"Could not send trade notification: {e}")
        
        # Emit trade update
        try:
            from app import socketio
            socketio.emit('trade_executed', {
                'trade_id': transaction.id,
                'amount': trade_amount,
                'price': trade_price,
                'total_price': total_price,
                'buyer_id': buy_order.user_id,
                'seller_id': sell_order.user_id
            }, to='marketplace_updates')
        except Exception as e:
            print(f"Could not emit trade update: {e}")
        
        return transaction
    
    @staticmethod
    def get_order_book():
        """Get current market order book"""
        # Get top 10 buy orders (highest prices first)
        buy_orders = TradeOrder.query.filter_by(
            order_type='buy', 
            status='active'
        ).order_by(TradeOrder.price_per_credit.desc()).limit(10).all()
        
        # Get top 10 sell orders (lowest prices first)
        sell_orders = TradeOrder.query.filter_by(
            order_type='sell', 
            status='active'
        ).order_by(TradeOrder.price_per_credit.asc()).limit(10).all()
        
        return {
            'buy_orders': [{
                'id': order.id,
                'amount': order.amount,
                'price_per_credit': order.price_per_credit,
                'total_value': order.amount * order.price_per_credit,
                'created_at': order.created_at.isoformat()
            } for order in buy_orders],
            'sell_orders': [{
                'id': order.id,
                'amount': order.amount,
                'price_per_credit': order.price_per_credit,
                'total_value': order.amount * order.price_per_credit,
                'created_at': order.created_at.isoformat()
            } for order in sell_orders]
        }
    
    @staticmethod
    def get_market_stats():
        """Get marketplace statistics"""
        # Recent transactions for price analysis
        recent_transactions = TradeTransaction.query.order_by(
            TradeTransaction.executed_at.desc()
        ).limit(100).all()
        
        if not recent_transactions:
            return {
                'total_volume': 0,
                'average_price': 0,
                'price_change_24h': 0,
                'active_orders': TradeOrder.query.filter_by(status='active').count(),
                'total_trades': 0
            }
        
        # Calculate statistics
        total_volume = sum(tx.total_price for tx in recent_transactions)
        average_price = sum(tx.price_per_credit for tx in recent_transactions) / len(recent_transactions)
        
        # Calculate 24h price change
        from datetime import timedelta
        yesterday = datetime.utcnow() - timedelta(hours=24)
        
        recent_24h = [tx for tx in recent_transactions if tx.executed_at >= yesterday]
        older_24h = [tx for tx in recent_transactions if tx.executed_at < yesterday]
        
        if recent_24h and older_24h:
            recent_avg = sum(tx.price_per_credit for tx in recent_24h) / len(recent_24h)
            older_avg = sum(tx.price_per_credit for tx in older_24h) / len(older_24h)
            price_change_24h = ((recent_avg - older_avg) / older_avg) * 100
        else:
            price_change_24h = 0
        
        active_orders = TradeOrder.query.filter_by(status='active').count()
        total_trades = TradeTransaction.query.count()
        
        return {
            'total_volume': total_volume,
            'average_price': average_price,
            'price_change_24h': price_change_24h,
            'active_orders': active_orders,
            'total_trades': total_trades,
            'volume_24h': sum(tx.total_price for tx in recent_24h) if recent_24h else 0
        }
    
    @staticmethod
    def get_user_orders(user_id):
        """Get all orders for a specific user"""
        return TradeOrder.query.filter_by(user_id=user_id).order_by(
            TradeOrder.created_at.desc()
        ).all()
    
    @staticmethod
    def get_user_transactions(user_id):
        """Get all transactions for a specific user"""
        return TradeTransaction.query.filter(
            or_(
                TradeTransaction.buyer_id == user_id,
                TradeTransaction.seller_id == user_id
            )
        ).order_by(TradeTransaction.executed_at.desc()).all()
