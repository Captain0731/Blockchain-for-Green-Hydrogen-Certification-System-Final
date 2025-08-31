import json
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notification_preferences = db.Column(db.Text)
    
    # Relationships
    certificates = db.relationship('Certificate', backref='user', lazy=True)
    credits = db.relationship('Credit', backref='user', lazy=True)
    trade_orders = db.relationship('TradeOrder', backref='user', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def get_total_credits(self):
        """Calculate total credits for user"""
        total = 0
        # Import here to avoid circular import
        from models import Credit
        credits_list = Credit.query.filter_by(user_id=self.id).all()
        for credit in credits_list:
            if credit.transaction_type in ['add', 'transfer_in']:
                total += credit.amount
            elif credit.transaction_type in ['transfer_out', 'trade']:
                total -= credit.amount
        return max(0, total)  # Ensure non-negative
    
    def get_notification_preferences(self):
        """Get user notification preferences"""
        if self.notification_preferences:
            return json.loads(self.notification_preferences)
        return {
            'blockchain_events': True,
            'certificate_updates': True,
            'marketplace_activity': True,
            'system_alerts': True
        }
    
    def set_notification_preferences(self, preferences):
        """Set user notification preferences"""
        self.notification_preferences = json.dumps(preferences)

class Certificate(db.Model):
    __tablename__ = 'certificates'
    
    id = db.Column(db.Integer, primary_key=True)
    certificate_id = db.Column(db.String(128), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='issued')
    verification_status = db.Column(db.String(50), default='pending')
    smart_contract_address = db.Column(db.String(128))
    meta_data = db.Column(db.Text)
    
    def get_meta(self):
        """Get certificate metadata"""
        if self.meta_data:
            return json.loads(self.meta_data)
        return {}
    
    def set_meta(self, meta_dict):
        """Set certificate metadata"""
        self.meta_data = json.dumps(meta_dict)

class Credit(db.Model):
    __tablename__ = 'credits'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(50), nullable=False)  # add, transfer_in, transfer_out, trade
    date = db.Column(db.DateTime, default=datetime.utcnow)
    meta_data = db.Column(db.Text)
    
    def get_meta(self):
        """Get credit metadata"""
        if self.meta_data:
            return json.loads(self.meta_data)
        return {}
    
    def set_meta(self, meta_dict):
        """Set credit metadata"""
        self.meta_data = json.dumps(meta_dict)

class Block(db.Model):
    __tablename__ = 'blocks'
    
    id = db.Column(db.Integer, primary_key=True)
    index = db.Column(db.Integer, unique=True, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    data = db.Column(db.Text)
    previous_hash = db.Column(db.String(256))
    hash = db.Column(db.String(256), unique=True, nullable=False)
    nonce = db.Column(db.Integer, default=0)
    difficulty = db.Column(db.Integer, default=1)
    
    def get_transactions(self):
        """Get transactions from block data"""
        if self.data:
            return json.loads(self.data)
        return []
    
    def set_transactions(self, transactions):
        """Set block transactions"""
        self.data = json.dumps(transactions)

class TradeOrder(db.Model):
    __tablename__ = 'trade_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    order_type = db.Column(db.String(10), nullable=False)  # buy or sell
    amount = db.Column(db.Float, nullable=False)
    price_per_credit = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='active')  # active, filled, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    filled_at = db.Column(db.DateTime)

class TradeTransaction(db.Model):
    __tablename__ = 'trade_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    price_per_credit = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    buyer = db.relationship('User', foreign_keys=[buyer_id])
    seller = db.relationship('User', foreign_keys=[seller_id])

class SmartContract(db.Model):
    __tablename__ = 'smart_contracts'
    
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(128), unique=True, nullable=False)
    contract_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='active')
    code_hash = db.Column(db.String(256))
    deployed_at = db.Column(db.DateTime, default=datetime.utcnow)
    meta_data = db.Column(db.Text)
    
    def get_meta(self):
        """Get contract metadata"""
        if self.meta_data:
            return json.loads(self.meta_data)
        return {}
    
    def set_meta(self, meta_dict):
        """Set contract metadata"""
        self.meta_data = json.dumps(meta_dict)

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    meta_data = db.Column(db.Text)
    
    def get_meta(self):
        """Get notification metadata"""
        if self.meta_data:
            return json.loads(self.meta_data)
        return {}
    
    def set_meta(self, meta_dict):
        """Set notification metadata"""
        self.meta_data = json.dumps(meta_dict)
