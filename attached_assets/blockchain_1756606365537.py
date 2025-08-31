import hashlib
import json
import secrets
from datetime import datetime, timedelta
from app import db, socketio
from models import Block, SmartContract
from notifications import NotificationManager

class BlockchainSimulator:
    @staticmethod
    def calculate_hash(index, previous_hash, timestamp, transactions, nonce, difficulty=2):
        """Calculate the hash of a block"""
        block_string = f"{index}{previous_hash}{timestamp}{json.dumps(transactions)}{nonce}{difficulty}"
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    @staticmethod
    def mine_block(index, previous_hash, transactions, difficulty=2, miner_address=None):
        """Mine a new block with proof-of-work"""
        timestamp = datetime.utcnow().isoformat()
        nonce = 0
        target = "0" * difficulty
        
        start_time = datetime.utcnow()
        
        while True:
            hash_result = BlockchainSimulator.calculate_hash(index, previous_hash, timestamp, transactions, nonce, difficulty)
            if hash_result.startswith(target):
                mining_time = (datetime.utcnow() - start_time).total_seconds()
                return {
                    'index': index,
                    'previous_hash': previous_hash,
                    'timestamp': timestamp,
                    'transactions': transactions,
                    'nonce': nonce,
                    'hash': hash_result,
                    'difficulty': difficulty,
                    'miner_address': miner_address or f"miner_{secrets.token_hex(4)}",
                    'mining_time': mining_time
                }
            nonce += 1
            
            # Prevent infinite loops in case of high difficulty
            if nonce > 1000000:
                difficulty = max(1, difficulty - 1)
                nonce = 0
    
    @staticmethod
    def get_last_block():
        """Get the last block in the chain"""
        return Block.query.order_by(Block.index.desc()).first()
    
    @staticmethod
    def create_genesis_block():
        """Create the first block in the chain"""
        existing_genesis = Block.query.filter_by(index=0).first()
        if existing_genesis:
            return existing_genesis
        
        transactions = [{"type": "genesis", "message": "Genesis block for Enhanced Green Hydrogen Platform"}]
        block_data = BlockchainSimulator.mine_block(0, "0", transactions, difficulty=1)
        
        genesis_block = Block(
            index=0,
            previous_hash="0",
            timestamp=datetime.fromisoformat(block_data['timestamp']),
            nonce=block_data['nonce'],
            hash=block_data['hash'],
            difficulty=1,
            miner_address=block_data['miner_address']
        )
        genesis_block.set_transactions(transactions)
        
        db.session.add(genesis_block)
        db.session.commit()
        return genesis_block
    
    @staticmethod
    def add_block(transactions, miner_address=None):
        """Add a new block to the chain"""
        last_block = BlockchainSimulator.get_last_block()
        if not last_block:
            last_block = BlockchainSimulator.create_genesis_block()
        
        # Dynamic difficulty adjustment
        difficulty = BlockchainSimulator.calculate_difficulty()
        
        new_index = last_block.index + 1
        block_data = BlockchainSimulator.mine_block(new_index, last_block.hash, transactions, difficulty, miner_address)
        
        new_block = Block(
            index=new_index,
            previous_hash=last_block.hash,
            timestamp=datetime.fromisoformat(block_data['timestamp']),
            nonce=block_data['nonce'],
            hash=block_data['hash'],
            difficulty=difficulty,
            miner_address=block_data['miner_address']
        )
        new_block.set_transactions(transactions)
        
        db.session.add(new_block)
        db.session.commit()
        
        # Emit real-time update
        socketio.emit('new_block', {
            'index': new_block.index,
            'hash': new_block.hash,
            'transactions': new_block.get_transactions(),
            'timestamp': new_block.timestamp.isoformat(),
            'mining_time': block_data.get('mining_time', 0)
        })
        
        # Send notifications for blockchain events
        NotificationManager.send_blockchain_notification(new_block)
        
        return new_block
    
    @staticmethod
    def calculate_difficulty():
        """Calculate difficulty based on recent block times"""
        recent_blocks = Block.query.order_by(Block.index.desc()).limit(10).all()
        if len(recent_blocks) < 2:
            return 2
        
        # Calculate average mining time for recent blocks
        time_diffs = []
        for i in range(len(recent_blocks) - 1):
            diff = (recent_blocks[i].timestamp - recent_blocks[i + 1].timestamp).total_seconds()
            time_diffs.append(diff)
        
        avg_time = sum(time_diffs) / len(time_diffs)
        target_time = 10.0  # Target 10 seconds per block
        
        current_difficulty = recent_blocks[0].difficulty
        
        if avg_time < target_time * 0.8:
            return min(6, current_difficulty + 1)
        elif avg_time > target_time * 1.2:
            return max(1, current_difficulty - 1)
        
        return current_difficulty
    
    @staticmethod
    def validate_chain():
        """Validate the entire blockchain"""
        blocks = Block.query.order_by(Block.index).all()
        
        for i, block in enumerate(blocks):
            if i == 0:  # Genesis block
                continue
            
            previous_block = blocks[i - 1]
            
            # Check if previous hash matches
            if block.previous_hash != previous_block.hash:
                return False, f"Invalid previous hash at block {block.index}"
            
            # Recalculate hash
            calculated_hash = BlockchainSimulator.calculate_hash(
                block.index, block.previous_hash, block.timestamp.isoformat(),
                block.get_transactions(), block.nonce, block.difficulty
            )
            
            if calculated_hash != block.hash:
                return False, f"Invalid hash at block {block.index}"
            
            # Check proof of work
            if not block.hash.startswith("0" * block.difficulty):
                return False, f"Invalid proof of work at block {block.index}"
        
        return True, "Blockchain is valid"
    
    @staticmethod
    def get_blockchain_stats():
        """Get comprehensive blockchain statistics"""
        total_blocks = Block.query.count()
        if total_blocks == 0:
            BlockchainSimulator.create_genesis_block()
            total_blocks = 1
        
        latest_block = BlockchainSimulator.get_last_block()
        
        # Calculate total transactions
        total_transactions = 0
        all_blocks = Block.query.all()
        for block in all_blocks:
            total_transactions += len(block.get_transactions())
        
        # Calculate average block time
        recent_blocks = Block.query.order_by(Block.index.desc()).limit(10).all()
        avg_block_time = 0
        if len(recent_blocks) > 1:
            time_diffs = []
            for i in range(len(recent_blocks) - 1):
                diff = (recent_blocks[i].timestamp - recent_blocks[i + 1].timestamp).total_seconds()
                time_diffs.append(diff)
            avg_block_time = sum(time_diffs) / len(time_diffs)
        
        # Network hash rate estimation (simplified)
        current_difficulty = latest_block.difficulty if latest_block else 2
        hash_rate = (2 ** current_difficulty) / max(avg_block_time, 1)
        
        return {
            'total_blocks': total_blocks,
            'total_transactions': total_transactions,
            'latest_block': latest_block,
            'current_difficulty': current_difficulty,
            'average_block_time': round(avg_block_time, 2),
            'estimated_hash_rate': round(hash_rate, 2),
            'chain_valid': BlockchainSimulator.validate_chain()[0]
        }
    
    @staticmethod
    def get_transaction_history(limit=50):
        """Get recent transaction history"""
        blocks = Block.query.order_by(Block.index.desc()).limit(limit).all()
        transactions = []
        
        for block in blocks:
            block_transactions = block.get_transactions()
            for tx in block_transactions:
                tx['block_index'] = block.index
                tx['block_hash'] = block.hash
                tx['block_timestamp'] = block.timestamp.isoformat()
                transactions.append(tx)
        
        return transactions
