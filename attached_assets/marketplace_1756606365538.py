from datetime import datetime
from app import db, socketio
from models import TradeOrder, MarketTransaction, Credit, User
from notifications import NotificationManager

class CarbonCreditMarketplace:
    
    @staticmethod
    def create_order(user_id, order_type, amount, price_per_credit, meta_data=None):
        """Create a new trade order"""
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"
        
        # Validate sell orders - user must have enough credits
        if order_type == 'sell':
            available_credits = user.get_total_credits()
            if available_credits < amount:
                return False, "Insufficient credits to sell"
        
        order = TradeOrder(
            user_id=user_id,
            order_type=order_type,
            amount=amount,
            price_per_credit=price_per_credit
        )
        
        if meta_data:
            order.set_meta(meta_data)
        
        db.session.add(order)
        db.session.commit()
        
        # Try to match the order immediately
        CarbonCreditMarketplace.match_orders()
        
        # Emit real-time update
        socketio.emit('new_order', {
            'id': order.id,
            'user_id': order.user_id,
            'order_type': order.order_type,
            'amount': order.amount,
            'price_per_credit': order.price_per_credit,
            'status': order.status,
            'created_at': order.created_at.isoformat()
        })
        
        return True, order
    
    @staticmethod
    def cancel_order(order_id, user_id):
        """Cancel a trade order"""
        order = TradeOrder.query.filter_by(id=order_id, user_id=user_id).first()
        if not order:
            return False, "Order not found"
        
        if order.status != 'open':
            return False, "Cannot cancel non-open order"
        
        order.status = 'cancelled'
        db.session.commit()
        
        # Emit real-time update
        socketio.emit('order_cancelled', {
            'order_id': order_id,
            'user_id': user_id
        })
        
        return True, "Order cancelled successfully"
    
    @staticmethod
    def match_orders():
        """Match buy and sell orders"""
        # Get all open buy orders (highest price first)
        buy_orders = TradeOrder.query.filter_by(
            order_type='buy', 
            status='open'
        ).order_by(TradeOrder.price_per_credit.desc()).all()
        
        # Get all open sell orders (lowest price first)
        sell_orders = TradeOrder.query.filter_by(
            order_type='sell', 
            status='open'
        ).order_by(TradeOrder.price_per_credit.asc()).all()
        
        for buy_order in buy_orders:
            for sell_order in sell_orders:
                if buy_order.price_per_credit >= sell_order.price_per_credit:
                    # Execute trade
                    trade_amount = min(buy_order.amount, sell_order.amount)
                    trade_price = sell_order.price_per_credit  # Seller's price
                    
                    success = CarbonCreditMarketplace._execute_trade(
                        buy_order, sell_order, trade_amount, trade_price
                    )
                    
                    if success:
                        # Update order amounts
                        buy_order.amount -= trade_amount
                        sell_order.amount -= trade_amount
                        
                        # Mark orders as completed if fully filled
                        if buy_order.amount == 0:
                            buy_order.status = 'completed'
                            buy_order.completed_at = datetime.utcnow()
                        
                        if sell_order.amount == 0:
                            sell_order.status = 'completed'
                            sell_order.completed_at = datetime.utcnow()
                        
                        db.session.commit()
                        
                        # Break inner loop if buy order is fully filled
                        if buy_order.amount == 0:
                            break
    
    @staticmethod
    def _execute_trade(buy_order, sell_order, amount, price_per_credit):
        """Execute a trade between two orders"""
        buyer = User.query.get(buy_order.user_id)
        seller = User.query.get(sell_order.user_id)
        
        if not buyer or not seller:
            return False
        
        # Verify seller has enough credits
        if seller.get_total_credits() < amount:
            return False
        
        total_price = amount * price_per_credit
        
        # Create market transaction record
        transaction = MarketTransaction(
            buyer_id=buyer.id,
            seller_id=seller.id,
            amount=amount,
            price_per_credit=price_per_credit,
            total_price=total_price,
            buyer_order_id=buy_order.id,
            seller_order_id=sell_order.id
        )
        
        # Transfer credits from seller to buyer
        seller_credit = Credit(
            user_id=seller.id,
            amount=amount,
            transaction_type='transfer_out'
        )
        seller_credit.set_meta({
            'transaction_id': 'pending',  # Will be updated after commit
            'buyer_id': buyer.id,
            'buyer_username': buyer.username,
            'price_per_credit': price_per_credit,
            'total_price': total_price,
            'description': f'Marketplace sale to {buyer.username}'
        })
        
        buyer_credit = Credit(
            user_id=buyer.id,
            amount=amount,
            transaction_type='transfer_in'
        )
        buyer_credit.set_meta({
            'transaction_id': 'pending',  # Will be updated after commit
            'seller_id': seller.id,
            'seller_username': seller.username,
            'price_per_credit': price_per_credit,
            'total_price': total_price,
            'description': f'Marketplace purchase from {seller.username}'
        })
        
        db.session.add(transaction)
        db.session.add(seller_credit)
        db.session.add(buyer_credit)
        db.session.commit()
        
        # Update credit records with transaction ID
        seller_credit_meta = seller_credit.get_meta()
        seller_credit_meta['transaction_id'] = transaction.id
        seller_credit.set_meta(seller_credit_meta)
        
        buyer_credit_meta = buyer_credit.get_meta()
        buyer_credit_meta['transaction_id'] = transaction.id
        buyer_credit.set_meta(buyer_credit_meta)
        
        db.session.commit()
        
        # Send notifications
        NotificationManager.send_trade_notification(transaction)
        
        # Emit real-time update
        socketio.emit('trade_executed', {
            'transaction_id': transaction.id,
            'buyer_id': buyer.id,
            'seller_id': seller.id,
            'amount': amount,
            'price_per_credit': price_per_credit,
            'total_price': total_price,
            'timestamp': transaction.transaction_date.isoformat()
        })
        
        return True
    
    @staticmethod
    def get_market_stats():
        """Get marketplace statistics"""
        # Total volume (last 30 days)
        from datetime import timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        recent_transactions = MarketTransaction.query.filter(
            MarketTransaction.transaction_date >= thirty_days_ago
        ).all()
        
        total_volume = sum(tx.amount for tx in recent_transactions)
        total_value = sum(tx.total_price for tx in recent_transactions)
        
        # Current market prices
        recent_prices = [tx.price_per_credit for tx in recent_transactions[-10:]]
        avg_price = sum(recent_prices) / len(recent_prices) if recent_prices else 0
        
        # Active orders
        open_orders = TradeOrder.query.filter_by(status='open').count()
        buy_orders = TradeOrder.query.filter_by(status='open', order_type='buy').count()
        sell_orders = TradeOrder.query.filter_by(status='open', order_type='sell').count()
        
        # Best prices
        best_buy = TradeOrder.query.filter_by(
            status='open', order_type='buy'
        ).order_by(TradeOrder.price_per_credit.desc()).first()
        
        best_sell = TradeOrder.query.filter_by(
            status='open', order_type='sell'
        ).order_by(TradeOrder.price_per_credit.asc()).first()
        
        return {
            'total_volume_30d': round(total_volume, 2),
            'total_value_30d': round(total_value, 2),
            'average_price': round(avg_price, 2),
            'active_orders': open_orders,
            'buy_orders': buy_orders,
            'sell_orders': sell_orders,
            'best_buy_price': best_buy.price_per_credit if best_buy else 0,
            'best_sell_price': best_sell.price_per_credit if best_sell else 0,
            'spread': (best_sell.price_per_credit - best_buy.price_per_credit) if (best_buy and best_sell) else 0
        }
    
    @staticmethod
    def get_order_book(limit=10):
        """Get current order book"""
        buy_orders = TradeOrder.query.filter_by(
            status='open', order_type='buy'
        ).order_by(TradeOrder.price_per_credit.desc()).limit(limit).all()
        
        sell_orders = TradeOrder.query.filter_by(
            status='open', order_type='sell'
        ).order_by(TradeOrder.price_per_credit.asc()).limit(limit).all()
        
        return {
            'buy_orders': [{
                'price': order.price_per_credit,
                'amount': order.amount,
                'total': order.price_per_credit * order.amount
            } for order in buy_orders],
            'sell_orders': [{
                'price': order.price_per_credit,
                'amount': order.amount,
                'total': order.price_per_credit * order.amount
            } for order in sell_orders]
        }
    
    @staticmethod
    def get_user_orders(user_id, status=None):
        """Get user's orders"""
        query = TradeOrder.query.filter_by(user_id=user_id)
        if status:
            query = query.filter_by(status=status)
        
        return query.order_by(TradeOrder.created_at.desc()).all()
    
    @staticmethod
    def get_user_transactions(user_id, limit=50):
        """Get user's market transactions"""
        transactions = MarketTransaction.query.filter(
            (MarketTransaction.buyer_id == user_id) | 
            (MarketTransaction.seller_id == user_id)
        ).order_by(MarketTransaction.transaction_date.desc()).limit(limit).all()
        
        return transactions
