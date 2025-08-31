from datetime import datetime
from app import db, socketio
from models import Notification, User

class NotificationManager:
    
    @staticmethod
    def create_notification(user_id, title, message, notification_type, meta_data=None):
        """Create a new notification"""
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type
        )
        
        if meta_data:
            notification.set_meta(meta_data)
        
        db.session.add(notification)
        db.session.commit()
        
        # Emit real-time notification
        socketio.emit('new_notification', {
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'timestamp': notification.created_at.isoformat()
        }, room=f'user_{user_id}')
        
        return notification
    
    @staticmethod
    def send_blockchain_notification(block):
        """Send notifications for blockchain events"""
        # Get users who want blockchain notifications
        users = User.query.all()
        
        for user in users:
            prefs = user.get_notification_preferences()
            if prefs.get('blockchain_events', True):
                # Check if user has transactions in this block
                transactions = block.get_transactions()
                user_involved = any(
                    tx.get('user_id') == user.id or 
                    tx.get('from_user_id') == user.id or 
                    tx.get('to_user_id') == user.id
                    for tx in transactions
                )
                
                if user_involved:
                    NotificationManager.create_notification(
                        user.id,
                        'Blockchain Transaction Confirmed',
                        f'Your transaction has been confirmed in block #{block.index}',
                        'blockchain_confirmation',
                        {
                            'block_index': block.index,
                            'block_hash': block.hash,
                            'transaction_count': len(transactions)
                        }
                    )
    
    @staticmethod
    def send_certificate_notification(certificate, event_type):
        """Send notifications for certificate events"""
        user = User.query.get(certificate.user_id)
        if not user:
            return
        
        prefs = user.get_notification_preferences()
        if not prefs.get('certificate_updates', True):
            return
        
        if event_type == 'issued':
            title = 'Certificate Issued'
            message = f'Your hydrogen certificate {certificate.certificate_id} has been issued successfully'
        elif event_type == 'verified':
            title = 'Certificate Verified'
            message = f'Your certificate {certificate.certificate_id} has been verified by smart contract'
        elif event_type == 'rejected':
            title = 'Certificate Verification Failed'
            message = f'Your certificate {certificate.certificate_id} failed verification'
        else:
            return
        
        NotificationManager.create_notification(
            user.id,
            title,
            message,
            'certificate_update',
            {
                'certificate_id': certificate.certificate_id,
                'event_type': event_type,
                'verification_status': certificate.verification_status
            }
        )
    
    @staticmethod
    def send_trade_notification(transaction):
        """Send notifications for marketplace trades"""
        # Notify buyer
        buyer = User.query.get(transaction.buyer_id)
        if buyer:
            buyer_prefs = buyer.get_notification_preferences()
            if buyer_prefs.get('marketplace_activity', True):
                NotificationManager.create_notification(
                    buyer.id,
                    'Trade Executed - Purchase',
                    f'You bought {transaction.amount} credits at ${transaction.price_per_credit:.2f} each',
                    'trade_executed',
                    {
                        'transaction_id': transaction.id,
                        'role': 'buyer',
                        'amount': transaction.amount,
                        'price_per_credit': transaction.price_per_credit,
                        'total_price': transaction.total_price
                    }
                )
        
        # Notify seller
        seller = User.query.get(transaction.seller_id)
        if seller:
            seller_prefs = seller.get_notification_preferences()
            if seller_prefs.get('marketplace_activity', True):
                NotificationManager.create_notification(
                    seller.id,
                    'Trade Executed - Sale',
                    f'You sold {transaction.amount} credits at ${transaction.price_per_credit:.2f} each',
                    'trade_executed',
                    {
                        'transaction_id': transaction.id,
                        'role': 'seller',
                        'amount': transaction.amount,
                        'price_per_credit': transaction.price_per_credit,
                        'total_price': transaction.total_price
                    }
                )
    
    @staticmethod
    def send_system_notification(title, message, notification_type='system_alert', target_users=None):
        """Send system-wide notifications"""
        if target_users is None:
            # Send to all users who want system alerts
            users = User.query.all()
            target_users = [user for user in users if user.get_notification_preferences().get('system_alerts', True)]
        
        for user in target_users:
            NotificationManager.create_notification(
                user.id,
                title,
                message,
                notification_type
            )
    
    @staticmethod
    def mark_as_read(notification_id, user_id):
        """Mark a notification as read"""
        notification = Notification.query.filter_by(
            id=notification_id, 
            user_id=user_id
        ).first()
        
        if notification:
            notification.is_read = True
            db.session.commit()
            return True
        
        return False
    
    @staticmethod
    def mark_all_as_read(user_id):
        """Mark all notifications as read for a user"""
        notifications = Notification.query.filter_by(
            user_id=user_id, 
            is_read=False
        ).all()
        
        for notification in notifications:
            notification.is_read = True
        
        db.session.commit()
        return len(notifications)
    
    @staticmethod
    def get_user_notifications(user_id, limit=50, unread_only=False):
        """Get user's notifications"""
        query = Notification.query.filter_by(user_id=user_id)
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        return query.order_by(Notification.created_at.desc()).limit(limit).all()
    
    @staticmethod
    def get_unread_count(user_id):
        """Get count of unread notifications"""
        return Notification.query.filter_by(
            user_id=user_id, 
            is_read=False
        ).count()
    
    @staticmethod
    def delete_notification(notification_id, user_id):
        """Delete a notification"""
        notification = Notification.query.filter_by(
            id=notification_id, 
            user_id=user_id
        ).first()
        
        if notification:
            db.session.delete(notification)
            db.session.commit()
            return True
        
        return False
    
    @staticmethod
    def cleanup_old_notifications(days=30):
        """Clean up old notifications"""
        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        old_notifications = Notification.query.filter(
            Notification.created_at < cutoff_date,
            Notification.is_read == True
        ).all()
        
        count = len(old_notifications)
        for notification in old_notifications:
            db.session.delete(notification)
        
        db.session.commit()
        return count
