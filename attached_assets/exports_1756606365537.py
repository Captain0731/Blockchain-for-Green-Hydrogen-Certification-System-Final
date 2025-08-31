import csv
import json
from datetime import datetime
from io import StringIO
from flask import make_response
from models import Certificate, Credit, MarketTransaction, Block

class ExportManager:
    
    @staticmethod
    def export_certificates_csv(user_id):
        """Export user's certificates to CSV"""
        certificates = Certificate.query.filter_by(user_id=user_id).all()
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Certificate ID', 'Issue Date', 'Status', 'Verification Status',
            'Hydrogen Amount (kg)', 'Production Method', 'Location',
            'Carbon Intensity', 'Smart Contract Address'
        ])
        
        # Write data
        for cert in certificates:
            meta = cert.get_meta()
            writer.writerow([
                cert.certificate_id,
                cert.issue_date.strftime('%Y-%m-%d %H:%M:%S'),
                cert.status,
                cert.verification_status,
                meta.get('hydrogen_amount_kg', ''),
                meta.get('production_method', ''),
                meta.get('location', ''),
                meta.get('carbon_intensity', ''),
                cert.smart_contract_address or ''
            ])
        
        output.seek(0)
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=certificates_{datetime.now().strftime("%Y%m%d")}.csv'
        
        return response
    
    @staticmethod
    def export_credits_csv(user_id):
        """Export user's credit transactions to CSV"""
        credits = Credit.query.filter_by(user_id=user_id).order_by(Credit.date.desc()).all()
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Transaction ID', 'Date', 'Amount', 'Transaction Type',
            'Description', 'Source/Recipient', 'Balance After'
        ])
        
        # Calculate running balance
        running_balance = 0
        for credit in reversed(credits):
            if credit.transaction_type == 'add':
                running_balance += credit.amount
            elif credit.transaction_type == 'transfer_out':
                running_balance -= credit.amount
            elif credit.transaction_type == 'transfer_in':
                running_balance += credit.amount
        
        # Write data (reverse again to show most recent first)
        current_balance = running_balance
        for credit in credits:
            meta = credit.get_meta()
            
            # Adjust balance calculation for display
            if credit.transaction_type == 'add':
                current_balance -= credit.amount
            elif credit.transaction_type == 'transfer_out':
                current_balance += credit.amount
            elif credit.transaction_type == 'transfer_in':
                current_balance -= credit.amount
            
            balance_after = current_balance + (
                credit.amount if credit.transaction_type in ['add', 'transfer_in'] 
                else -credit.amount if credit.transaction_type == 'transfer_out' else 0
            )
            
            writer.writerow([
                credit.id,
                credit.date.strftime('%Y-%m-%d %H:%M:%S'),
                credit.amount,
                credit.transaction_type,
                meta.get('description', ''),
                meta.get('recipient_username', meta.get('sender_username', meta.get('source', ''))),
                round(balance_after, 2)
            ])
        
        output.seek(0)
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=credits_{datetime.now().strftime("%Y%m%d")}.csv'
        
        return response
    
    @staticmethod
    def export_market_transactions_csv(user_id):
        """Export user's market transactions to CSV"""
        transactions = MarketTransaction.query.filter(
            (MarketTransaction.buyer_id == user_id) | 
            (MarketTransaction.seller_id == user_id)
        ).order_by(MarketTransaction.transaction_date.desc()).all()
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Transaction ID', 'Date', 'Type', 'Amount', 'Price per Credit',
            'Total Price', 'Counterparty', 'Status'
        ])
        
        # Write data
        for tx in transactions:
            transaction_type = 'Buy' if tx.buyer_id == user_id else 'Sell'
            counterparty = tx.seller.username if tx.buyer_id == user_id else tx.buyer.username
            
            writer.writerow([
                tx.id,
                tx.transaction_date.strftime('%Y-%m-%d %H:%M:%S'),
                transaction_type,
                tx.amount,
                tx.price_per_credit,
                tx.total_price,
                counterparty,
                'Completed'
            ])
        
        output.seek(0)
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=market_transactions_{datetime.now().strftime("%Y%m%d")}.csv'
        
        return response
    
    @staticmethod
    def export_certificates_json(user_id):
        """Export user's certificates to JSON"""
        certificates = Certificate.query.filter_by(user_id=user_id).all()
        
        data = {
            'export_date': datetime.now().isoformat(),
            'user_id': user_id,
            'certificates': []
        }
        
        for cert in certificates:
            cert_data = {
                'certificate_id': cert.certificate_id,
                'issue_date': cert.issue_date.isoformat(),
                'status': cert.status,
                'verification_status': cert.verification_status,
                'smart_contract_address': cert.smart_contract_address,
                'meta': cert.get_meta()
            }
            data['certificates'].append(cert_data)
        
        response = make_response(json.dumps(data, indent=2))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename=certificates_{datetime.now().strftime("%Y%m%d")}.json'
        
        return response
    
    @staticmethod
    def export_blockchain_data_json(limit=100):
        """Export blockchain data to JSON"""
        blocks = Block.query.order_by(Block.index.desc()).limit(limit).all()
        
        data = {
            'export_date': datetime.now().isoformat(),
            'blockchain_data': []
        }
        
        for block in blocks:
            block_data = {
                'index': block.index,
                'hash': block.hash,
                'previous_hash': block.previous_hash,
                'timestamp': block.timestamp.isoformat(),
                'transactions': block.get_transactions(),
                'nonce': block.nonce,
                'difficulty': block.difficulty,
                'miner_address': block.miner_address
            }
            data['blockchain_data'].append(block_data)
        
        response = make_response(json.dumps(data, indent=2))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename=blockchain_data_{datetime.now().strftime("%Y%m%d")}.json'
        
        return response
    
    @staticmethod
    def generate_certificate_report(certificate_id):
        """Generate a detailed certificate report"""
        certificate = Certificate.query.filter_by(certificate_id=certificate_id).first()
        if not certificate:
            return None
        
        meta = certificate.get_meta()
        
        # Find related blockchain transactions
        related_blocks = Block.query.all()
        related_transactions = []
        
        for block in related_blocks:
            transactions = block.get_transactions()
            for tx in transactions:
                if (tx.get('certificate_id') == certificate_id or 
                    tx.get('user_id') == certificate.user_id):
                    tx['block_index'] = block.index
                    tx['block_hash'] = block.hash
                    related_transactions.append(tx)
        
        report_data = {
            'certificate': {
                'id': certificate.certificate_id,
                'issue_date': certificate.issue_date.isoformat(),
                'status': certificate.status,
                'verification_status': certificate.verification_status,
                'smart_contract_address': certificate.smart_contract_address,
                'user_id': certificate.user_id
            },
            'production_details': {
                'hydrogen_amount_kg': meta.get('hydrogen_amount_kg'),
                'production_method': meta.get('production_method'),
                'location': meta.get('location'),
                'carbon_intensity': meta.get('carbon_intensity')
            },
            'blockchain_trail': related_transactions,
            'verification_history': [
                {
                    'status': certificate.verification_status,
                    'contract_address': certificate.smart_contract_address,
                    'timestamp': certificate.issue_date.isoformat()
                }
            ],
            'report_generated': datetime.now().isoformat()
        }
        
        response = make_response(json.dumps(report_data, indent=2))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename=certificate_report_{certificate_id}.json'
        
        return response
