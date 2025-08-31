from datetime import datetime
import json
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_verified = db.Column(db.Boolean, default=False)
    notification_preferences = db.Column(db.Text, default='{}')
    
    # Relationships
    certificates = db.relationship('Certificate', backref='user', lazy=True)
    credits = db.relationship('Credit', backref='user', lazy=True)
    trade_orders = db.relationship('TradeOrder', backref='user', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_total_credits(self):
        total = 0
        for credit in self.credits:
            if credit.transaction_type == 'add':
                total += credit.amount
            elif credit.transaction_type == 'transfer_out':
                total -= credit.amount
            elif credit.transaction_type == 'transfer_in':
                total += credit.amount
        return max(0, total)
    
    def get_notification_preferences(self):
        if self.notification_preferences:
            return json.loads(self.notification_preferences)
        return {
            'blockchain_events': True,
            'certificate_updates': True,
            'marketplace_activity': True,
            'system_alerts': True
        }
    
    def set_notification_preferences(self, prefs):
        self.notification_preferences = json.dumps(prefs)

class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    certificate_id = db.Column(db.String(100), unique=True, nullable=False)
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')
    verification_status = db.Column(db.String(20), default='pending')
    smart_contract_address = db.Column(db.String(100))
    meta_json = db.Column(db.Text)
    
    def get_meta(self):
        if self.meta_json:
            return json.loads(self.meta_json)
        return {}
    
    def set_meta(self, data):
        self.meta_json = json.dumps(data)

class Credit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    meta_json = db.Column(db.Text)
    
    def get_meta(self):
        if self.meta_json:
            return json.loads(self.meta_json)
        return {}
    
    def set_meta(self, data):
        self.meta_json = json.dumps(data)

class Block(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    index = db.Column(db.Integer, unique=True, nullable=False)
    previous_hash = db.Column(db.String(64), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    transactions_json = db.Column(db.Text)
    nonce = db.Column(db.Integer, default=0)
    hash = db.Column(db.String(64), nullable=False)
    difficulty = db.Column(db.Integer, default=2)
    miner_address = db.Column(db.String(100))
    
    def get_transactions(self):
        if self.transactions_json:
            return json.loads(self.transactions_json)
        return []
    
    def set_transactions(self, transactions):
        self.transactions_json = json.dumps(transactions)

class SmartContract(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    address = db.Column(db.String(100), unique=True, nullable=False)
    contract_type = db.Column(db.String(50), nullable=False)
    deployment_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='active')
    code_hash = db.Column(db.String(64))
    meta_json = db.Column(db.Text)
    
    def get_meta(self):
        if self.meta_json:
            return json.loads(self.meta_json)
        return {}
    
    def set_meta(self, data):
        self.meta_json = json.dumps(data)

class TradeOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_type = db.Column(db.String(10), nullable=False)  # 'buy' or 'sell'
    amount = db.Column(db.Float, nullable=False)
    price_per_credit = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    meta_json = db.Column(db.Text)
    
    def get_meta(self):
        if self.meta_json:
            return json.loads(self.meta_json)
        return {}
    
    def set_meta(self, data):
        self.meta_json = json.dumps(data)

class MarketTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    price_per_credit = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    buyer_order_id = db.Column(db.Integer, db.ForeignKey('trade_order.id'))
    seller_order_id = db.Column(db.Integer, db.ForeignKey('trade_order.id'))
    
    buyer = db.relationship('User', foreign_keys=[buyer_id])
    seller = db.relationship('User', foreign_keys=[seller_id])

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    meta_json = db.Column(db.Text)
    
    def get_meta(self):
        if self.meta_json:
            return json.loads(self.meta_json)
        return {}
    
    def set_meta(self, data):
        self.meta_json = json.dumps(data)

class Analytics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    metric_name = db.Column(db.String(100), nullable=False)
    metric_value = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.Column(db.String(50))
    meta_json = db.Column(db.Text)
    
    def get_meta(self):
        if self.meta_json:
            return json.loads(self.meta_json)
        return {}
    
    def set_meta(self, data):
        self.meta_json = json.dumps(data)
