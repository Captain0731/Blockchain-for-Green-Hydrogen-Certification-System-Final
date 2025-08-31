from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from models import User, Certificate, Credit, Block, TradeTransaction, TradeOrder

class AnalyticsManager:
    """Analytics and reporting for the Green Hydrogen Platform"""
    
    @staticmethod
    def get_platform_overview():
        """Get comprehensive platform statistics"""
        # User statistics
        total_users = User.query.count()
        new_users_this_month = User.query.filter(
            User.created_at >= datetime.utcnow() - timedelta(days=30)
        ).count()
        
        # Certificate statistics
        total_certificates = Certificate.query.count()
        verified_certificates = Certificate.query.filter_by(verification_status='verified').count()
        pending_certificates = Certificate.query.filter_by(verification_status='pending').count()
        
        # Credit statistics
        total_credits = db.session.query(func.sum(Credit.amount)).filter(
            Credit.transaction_type.in_(['add', 'transfer_in'])
        ).scalar() or 0
        
        # Blockchain statistics
        total_blocks = Block.query.count()
        
        # Trading statistics
        total_trades = TradeTransaction.query.count()
        total_trade_volume = db.session.query(func.sum(TradeTransaction.total_price)).scalar() or 0
        active_orders = TradeOrder.query.filter_by(status='active').count()
        
        return {
            'users': {
                'total': total_users,
                'new_this_month': new_users_this_month,
                'growth_rate': (new_users_this_month / max(total_users - new_users_this_month, 1)) * 100
            },
            'certificates': {
                'total': total_certificates,
                'verified': verified_certificates,
                'pending': pending_certificates,
                'verification_rate': (verified_certificates / max(total_certificates, 1)) * 100
            },
            'credits': {
                'total': total_credits,
                'average_per_user': total_credits / max(total_users, 1)
            },
            'blockchain': {
                'total_blocks': total_blocks,
                'average_block_time': AnalyticsManager._calculate_average_block_time()
            },
            'marketplace': {
                'total_trades': total_trades,
                'total_volume': total_trade_volume,
                'active_orders': active_orders,
                'average_trade_size': (total_trade_volume / max(total_trades, 1)) if total_trades > 0 else 0
            }
        }
    
    @staticmethod
    def get_production_statistics():
        """Get hydrogen production statistics from certificates"""
        certificates = Certificate.query.all()
        
        production_by_method = {}
        total_hydrogen = 0
        carbon_intensity_data = []
        
        for cert in certificates:
            meta = cert.get_meta()
            method = meta.get('production_method', 'unknown')
            hydrogen_amount = meta.get('hydrogen_amount_kg', 0)
            carbon_intensity = meta.get('carbon_intensity', 0)
            
            if method not in production_by_method:
                production_by_method[method] = 0
            
            production_by_method[method] += hydrogen_amount
            total_hydrogen += hydrogen_amount
            
            if carbon_intensity is not None:
                carbon_intensity_data.append(carbon_intensity)
        
        avg_carbon_intensity = sum(carbon_intensity_data) / len(carbon_intensity_data) if carbon_intensity_data else 0
        
        return {
            'total_hydrogen_kg': total_hydrogen,
            'production_by_method': production_by_method,
            'average_carbon_intensity': avg_carbon_intensity,
            'total_certificates': len(certificates),
            'green_hydrogen_percentage': AnalyticsManager._calculate_green_percentage(certificates)
        }
    
    @staticmethod
    def get_carbon_analysis():
        """Analyze carbon impact and credits"""
        certificates = Certificate.query.all()
        
        total_co2_avoided = 0
        green_certificates = 0
        
        for cert in certificates:
            meta = cert.get_meta()
            production_method = meta.get('production_method', '')
            hydrogen_amount = meta.get('hydrogen_amount_kg', 0)
            carbon_intensity = meta.get('carbon_intensity', 0)
            
            # Calculate CO2 avoidance compared to grey hydrogen (10 kg CO2/kg H2)
            grey_hydrogen_emissions = hydrogen_amount * 10
            actual_emissions = hydrogen_amount * carbon_intensity
            co2_avoided = max(0, grey_hydrogen_emissions - actual_emissions)
            
            total_co2_avoided += co2_avoided
            
            if carbon_intensity <= 2.0:  # Green hydrogen threshold
                green_certificates += 1
        
        return {
            'total_co2_avoided_kg': total_co2_avoided,
            'green_certificates': green_certificates,
            'green_certificate_ratio': green_certificates / max(len(certificates), 1),
            'environmental_impact_score': min(100, total_co2_avoided / 100)  # Scaled score
        }
    
    @staticmethod
    def get_market_analysis():
        """Analyze marketplace activity and trends"""
        # Recent transactions (last 30 days)
        recent_cutoff = datetime.utcnow() - timedelta(days=30)
        recent_trades = TradeTransaction.query.filter(
            TradeTransaction.executed_at >= recent_cutoff
        ).all()
        
        # Calculate volume and price trends
        daily_volumes = {}
        price_history = []
        
        for trade in recent_trades:
            trade_date = trade.executed_at.date()
            if trade_date not in daily_volumes:
                daily_volumes[trade_date] = 0
            daily_volumes[trade_date] += trade.total_price
            price_history.append(trade.price_per_credit)
        
        # Current market state
        active_buy_orders = TradeOrder.query.filter_by(
            order_type='buy', status='active'
        ).count()
        
        active_sell_orders = TradeOrder.query.filter_by(
            order_type='sell', status='active'
        ).count()
        
        avg_price = sum(price_history) / len(price_history) if price_history else 0
        
        return {
            'recent_trades_count': len(recent_trades),
            'total_volume_30d': sum(daily_volumes.values()),
            'average_price': avg_price,
            'daily_volumes': dict(sorted(daily_volumes.items())),
            'active_orders': {
                'buy': active_buy_orders,
                'sell': active_sell_orders,
                'total': active_buy_orders + active_sell_orders
            },
            'market_liquidity': (active_buy_orders + active_sell_orders) / max(User.query.count(), 1)
        }
    
    @staticmethod
    def get_user_analytics(user_id):
        """Get analytics for a specific user"""
        user = User.query.get(user_id)
        if not user:
            return None
        
        # User's certificates
        user_certificates = Certificate.query.filter_by(user_id=user_id).all()
        verified_certs = [c for c in user_certificates if c.verification_status == 'verified']
        
        # User's credits
        user_credits = Credit.query.filter_by(user_id=user_id).all()
        total_credits = user.get_total_credits()
        
        # User's trading activity
        user_trades = TradeTransaction.query.filter(
            (TradeTransaction.buyer_id == user_id) | 
            (TradeTransaction.seller_id == user_id)
        ).all()
        
        # Calculate hydrogen production
        total_hydrogen = 0
        for cert in user_certificates:
            meta = cert.get_meta()
            total_hydrogen += meta.get('hydrogen_amount_kg', 0)
        
        return {
            'certificates': {
                'total': len(user_certificates),
                'verified': len(verified_certs),
                'verification_rate': len(verified_certs) / max(len(user_certificates), 1) * 100
            },
            'credits': {
                'total': total_credits,
                'transactions': len(user_credits)
            },
            'production': {
                'total_hydrogen_kg': total_hydrogen
            },
            'trading': {
                'total_trades': len(user_trades),
                'total_volume': sum(trade.total_price for trade in user_trades)
            }
        }
    
    @staticmethod
    def _calculate_average_block_time():
        """Calculate average time between blocks"""
        blocks = Block.query.order_by(Block.index).limit(10).all()
        if len(blocks) < 2:
            return 0
        
        time_diffs = []
        for i in range(1, len(blocks)):
            diff = (blocks[i].timestamp - blocks[i-1].timestamp).total_seconds()
            time_diffs.append(diff)
        
        return sum(time_diffs) / len(time_diffs) if time_diffs else 0
    
    @staticmethod
    def _calculate_green_percentage(certificates):
        """Calculate percentage of green hydrogen certificates"""
        if not certificates:
            return 0
        
        green_count = 0
        for cert in certificates:
            meta = cert.get_meta()
            carbon_intensity = meta.get('carbon_intensity', 0)
            if carbon_intensity <= 2.0:  # Green hydrogen threshold
                green_count += 1
        
        return (green_count / len(certificates)) * 100
