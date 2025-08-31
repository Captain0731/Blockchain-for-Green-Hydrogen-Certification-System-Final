from datetime import datetime, timedelta
from sqlalchemy import func
from app import db
from models import User, Certificate, Credit, Block, MarketTransaction, Analytics

class AnalyticsManager:
    
    @staticmethod
    def record_metric(metric_name, value, category=None, meta_data=None):
        """Record a new analytics metric"""
        metric = Analytics(
            metric_name=metric_name,
            metric_value=value,
            category=category
        )
        
        if meta_data:
            metric.set_meta(meta_data)
        
        db.session.add(metric)
        db.session.commit()
        
        return metric
    
    @staticmethod
    def get_platform_overview():
        """Get comprehensive platform overview"""
        # User statistics
        total_users = User.query.count()
        verified_users = User.query.filter_by(is_verified=True).count()
        
        # Calculate new users (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        new_users = User.query.filter(User.created_at >= thirty_days_ago).count()
        
        # Certificate statistics
        total_certificates = Certificate.query.count()
        verified_certificates = Certificate.query.filter_by(verification_status='verified').count()
        pending_certificates = Certificate.query.filter_by(verification_status='pending').count()
        
        # Credit statistics
        total_credits_issued = db.session.query(func.sum(Credit.amount)).filter(
            Credit.transaction_type == 'add'
        ).scalar() or 0
        
        total_credits_transferred = db.session.query(func.sum(Credit.amount)).filter(
            Credit.transaction_type == 'transfer_out'
        ).scalar() or 0
        
        # Blockchain statistics
        total_blocks = Block.query.count()
        total_transactions = 0
        for block in Block.query.all():
            total_transactions += len(block.get_transactions())
        
        # Market statistics
        market_volume_30d = db.session.query(func.sum(MarketTransaction.amount)).filter(
            MarketTransaction.transaction_date >= thirty_days_ago
        ).scalar() or 0
        
        market_value_30d = db.session.query(func.sum(MarketTransaction.total_price)).filter(
            MarketTransaction.transaction_date >= thirty_days_ago
        ).scalar() or 0
        
        return {
            'users': {
                'total': total_users,
                'verified': verified_users,
                'new_30d': new_users,
                'verification_rate': round((verified_users / max(total_users, 1)) * 100, 1)
            },
            'certificates': {
                'total': total_certificates,
                'verified': verified_certificates,
                'pending': pending_certificates,
                'verification_rate': round((verified_certificates / max(total_certificates, 1)) * 100, 1)
            },
            'credits': {
                'total_issued': round(total_credits_issued, 2),
                'total_transferred': round(total_credits_transferred, 2),
                'circulation': round(total_credits_issued - total_credits_transferred, 2)
            },
            'blockchain': {
                'total_blocks': total_blocks,
                'total_transactions': total_transactions,
                'avg_tx_per_block': round(total_transactions / max(total_blocks, 1), 2)
            },
            'marketplace': {
                'volume_30d': round(market_volume_30d, 2),
                'value_30d': round(market_value_30d, 2),
                'avg_price_30d': round(market_value_30d / max(market_volume_30d, 1), 2) if market_volume_30d > 0 else 0
            }
        }
    
    @staticmethod
    def get_time_series_data(metric_category, days=30):
        """Get time series data for charts"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Generate date range
        date_range = []
        current_date = start_date.date()
        end_date = datetime.utcnow().date()
        
        while current_date <= end_date:
            date_range.append(current_date)
            current_date += timedelta(days=1)
        
        data = {}
        
        if metric_category == 'users':
            data = AnalyticsManager._get_user_growth_data(date_range)
        elif metric_category == 'certificates':
            data = AnalyticsManager._get_certificate_data(date_range)
        elif metric_category == 'credits':
            data = AnalyticsManager._get_credits_data(date_range)
        elif metric_category == 'blockchain':
            data = AnalyticsManager._get_blockchain_data(date_range)
        elif metric_category == 'marketplace':
            data = AnalyticsManager._get_marketplace_data(date_range)
        
        return data
    
    @staticmethod
    def _get_user_growth_data(date_range):
        """Get user growth time series data"""
        labels = [date.strftime('%Y-%m-%d') for date in date_range]
        
        # Get cumulative user registrations
        registrations = []
        total_users = 0
        
        for date in date_range:
            day_start = datetime.combine(date, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            
            daily_registrations = User.query.filter(
                User.created_at >= day_start,
                User.created_at < day_end
            ).count()
            
            total_users += daily_registrations
            registrations.append(total_users)
        
        return {
            'labels': labels,
            'datasets': [{
                'label': 'Total Users',
                'data': registrations,
                'borderColor': 'rgb(34, 197, 94)',
                'backgroundColor': 'rgba(34, 197, 94, 0.1)',
                'fill': True
            }]
        }
    
    @staticmethod
    def _get_certificate_data(date_range):
        """Get certificate issuance time series data"""
        labels = [date.strftime('%Y-%m-%d') for date in date_range]
        
        daily_certificates = []
        cumulative_certificates = []
        total_certificates = 0
        
        for date in date_range:
            day_start = datetime.combine(date, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            
            daily_count = Certificate.query.filter(
                Certificate.issue_date >= day_start,
                Certificate.issue_date < day_end
            ).count()
            
            daily_certificates.append(daily_count)
            total_certificates += daily_count
            cumulative_certificates.append(total_certificates)
        
        return {
            'labels': labels,
            'datasets': [
                {
                    'label': 'Daily Certificates',
                    'data': daily_certificates,
                    'borderColor': 'rgb(59, 130, 246)',
                    'backgroundColor': 'rgba(59, 130, 246, 0.1)',
                    'type': 'bar'
                },
                {
                    'label': 'Cumulative Certificates',
                    'data': cumulative_certificates,
                    'borderColor': 'rgb(168, 85, 247)',
                    'backgroundColor': 'rgba(168, 85, 247, 0.1)',
                    'fill': True
                }
            ]
        }
    
    @staticmethod
    def _get_credits_data(date_range):
        """Get credits time series data"""
        labels = [date.strftime('%Y-%m-%d') for date in date_range]
        
        daily_credits_issued = []
        daily_credits_transferred = []
        
        for date in date_range:
            day_start = datetime.combine(date, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            
            credits_issued = db.session.query(func.sum(Credit.amount)).filter(
                Credit.date >= day_start,
                Credit.date < day_end,
                Credit.transaction_type == 'add'
            ).scalar() or 0
            
            credits_transferred = db.session.query(func.sum(Credit.amount)).filter(
                Credit.date >= day_start,
                Credit.date < day_end,
                Credit.transaction_type == 'transfer_out'
            ).scalar() or 0
            
            daily_credits_issued.append(round(credits_issued, 2))
            daily_credits_transferred.append(round(credits_transferred, 2))
        
        return {
            'labels': labels,
            'datasets': [
                {
                    'label': 'Credits Issued',
                    'data': daily_credits_issued,
                    'borderColor': 'rgb(34, 197, 94)',
                    'backgroundColor': 'rgba(34, 197, 94, 0.1)',
                    'type': 'bar'
                },
                {
                    'label': 'Credits Transferred',
                    'data': daily_credits_transferred,
                    'borderColor': 'rgb(239, 68, 68)',
                    'backgroundColor': 'rgba(239, 68, 68, 0.1)',
                    'type': 'bar'
                }
            ]
        }
    
    @staticmethod
    def _get_blockchain_data(date_range):
        """Get blockchain time series data"""
        labels = [date.strftime('%Y-%m-%d') for date in date_range]
        
        daily_blocks = []
        daily_transactions = []
        
        for date in date_range:
            day_start = datetime.combine(date, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            
            blocks_count = Block.query.filter(
                Block.timestamp >= day_start,
                Block.timestamp < day_end
            ).count()
            
            # Count transactions in blocks for this day
            day_blocks = Block.query.filter(
                Block.timestamp >= day_start,
                Block.timestamp < day_end
            ).all()
            
            tx_count = 0
            for block in day_blocks:
                tx_count += len(block.get_transactions())
            
            daily_blocks.append(blocks_count)
            daily_transactions.append(tx_count)
        
        return {
            'labels': labels,
            'datasets': [
                {
                    'label': 'Blocks Mined',
                    'data': daily_blocks,
                    'borderColor': 'rgb(168, 85, 247)',
                    'backgroundColor': 'rgba(168, 85, 247, 0.1)',
                    'type': 'bar'
                },
                {
                    'label': 'Transactions',
                    'data': daily_transactions,
                    'borderColor': 'rgb(245, 158, 11)',
                    'backgroundColor': 'rgba(245, 158, 11, 0.1)',
                    'type': 'line'
                }
            ]
        }
    
    @staticmethod
    def _get_marketplace_data(date_range):
        """Get marketplace time series data"""
        labels = [date.strftime('%Y-%m-%d') for date in date_range]
        
        daily_volume = []
        daily_value = []
        
        for date in date_range:
            day_start = datetime.combine(date, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            
            volume = db.session.query(func.sum(MarketTransaction.amount)).filter(
                MarketTransaction.transaction_date >= day_start,
                MarketTransaction.transaction_date < day_end
            ).scalar() or 0
            
            value = db.session.query(func.sum(MarketTransaction.total_price)).filter(
                MarketTransaction.transaction_date >= day_start,
                MarketTransaction.transaction_date < day_end
            ).scalar() or 0
            
            daily_volume.append(round(volume, 2))
            daily_value.append(round(value, 2))
        
        return {
            'labels': labels,
            'datasets': [
                {
                    'label': 'Trading Volume (Credits)',
                    'data': daily_volume,
                    'borderColor': 'rgb(34, 197, 94)',
                    'backgroundColor': 'rgba(34, 197, 94, 0.1)',
                    'yAxisID': 'y'
                },
                {
                    'label': 'Trading Value ($)',
                    'data': daily_value,
                    'borderColor': 'rgb(59, 130, 246)',
                    'backgroundColor': 'rgba(59, 130, 246, 0.1)',
                    'yAxisID': 'y1'
                }
            ]
        }
    
    @staticmethod
    def get_production_method_stats():
        """Get hydrogen production method statistics"""
        methods = {}
        certificates = Certificate.query.all()
        
        for cert in certificates:
            meta = cert.get_meta()
            method = meta.get('production_method', 'unknown')
            if method not in methods:
                methods[method] = {'count': 0, 'total_hydrogen': 0}
            
            methods[method]['count'] += 1
            methods[method]['total_hydrogen'] += meta.get('hydrogen_amount_kg', 0)
        
        return methods
    
    @staticmethod
    def get_carbon_intensity_analysis():
        """Get carbon intensity analysis"""
        certificates = Certificate.query.all()
        intensities = []
        
        for cert in certificates:
            meta = cert.get_meta()
            intensity = meta.get('carbon_intensity', 0)
            if intensity > 0:
                intensities.append(intensity)
        
        if not intensities:
            return {
                'average': 0,
                'min': 0,
                'max': 0,
                'green_percentage': 0
            }
        
        average = sum(intensities) / len(intensities)
        green_count = sum(1 for i in intensities if i <= 2.0)  # Green hydrogen threshold
        
        return {
            'average': round(average, 2),
            'min': round(min(intensities), 2),
            'max': round(max(intensities), 2),
            'green_percentage': round((green_count / len(intensities)) * 100, 1)
        }
