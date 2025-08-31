import hashlib
import json
from datetime import datetime
from app import db
from models import Block

class BlockchainSimulator:
    """Simulated blockchain for the Green Hydrogen Platform"""
    
    @staticmethod
    def calculate_hash(index, previous_hash, data, transactions, nonce):
        """Calculate block hash"""
        block_string = f"{index}{previous_hash}{data}{json.dumps(transactions)}{nonce}"
        return hashlib.sha256(block_string.encode()).hexdigest()
    
    @staticmethod
    def mine_block(index, previous_hash, transactions, difficulty=2):
        """Mine a new block with proof of work"""
        nonce = 0
        target = "0" * difficulty
        
        while True:
            data = json.dumps(transactions)
            current_hash = BlockchainSimulator.calculate_hash(index, previous_hash, data, transactions, nonce)
            
            if current_hash.startswith(target):
                return current_hash, nonce
            
            nonce += 1
            
            # Prevent infinite loops in development
            if nonce > 100000:
                break
        
        # Fallback if mining takes too long
        data = json.dumps(transactions)
        return BlockchainSimulator.calculate_hash(index, previous_hash, data, transactions, nonce), nonce
    
    @staticmethod
    def get_latest_block():
        """Get the latest block from the database"""
        return Block.query.order_by(Block.index.desc()).first()
    
    @staticmethod
    def add_block(transactions, miner_id=None):
        """Add a new block to the blockchain"""
        latest_block = BlockchainSimulator.get_latest_block()
        
        if latest_block is None:
            # Genesis block
            index = 0
            previous_hash = "0"
        else:
            index = latest_block.index + 1
            previous_hash = latest_block.hash
        
        # Mine the block
        difficulty = 2  # Adjustable difficulty
        block_hash, nonce = BlockchainSimulator.mine_block(index, previous_hash, transactions, difficulty)
        
        # Create new block
        new_block = Block()
        new_block.index = index
        new_block.timestamp = datetime.utcnow()
        new_block.previous_hash = previous_hash
        new_block.hash = block_hash
        new_block.nonce = nonce
        new_block.difficulty = difficulty
        new_block.set_transactions(transactions)
        
        db.session.add(new_block)
        db.session.commit()
        
        # Emit blockchain update via SocketIO if available
        try:
            from app import socketio
            socketio.emit('new_block', {
                'index': new_block.index,
                'hash': new_block.hash,
                'timestamp': new_block.timestamp.isoformat(),
                'transaction_count': len(transactions),
                'difficulty': difficulty,
                'miner': miner_id
            }, to='blockchain_updates')
        except Exception as e:
            print(f"Could not emit blockchain update: {e}")
        
        return new_block
    
    @staticmethod
    def validate_chain():
        """Validate the entire blockchain"""
        blocks = Block.query.order_by(Block.index).all()
        
        for i, block in enumerate(blocks):
            # Check genesis block
            if i == 0:
                if block.index != 0 or block.previous_hash != "0":
                    return False
                continue
            
            previous_block = blocks[i - 1]
            
            # Check if current block points to previous block
            if block.previous_hash != previous_block.hash:
                return False
            
            # Verify block hash
            transactions = block.get_transactions()
            calculated_hash = BlockchainSimulator.calculate_hash(
                block.index, 
                block.previous_hash, 
                block.data, 
                transactions, 
                block.nonce
            )
            
            if calculated_hash != block.hash:
                return False
        
        return True
    
    @staticmethod
    def get_blockchain_stats():
        """Get blockchain statistics"""
        total_blocks = Block.query.count()
        latest_block = BlockchainSimulator.get_latest_block()
        
        total_transactions = 0
        if latest_block:
            # Count all transactions across all blocks
            blocks = Block.query.all()
            for block in blocks:
                total_transactions += len(block.get_transactions())
        
        return {
            'total_blocks': total_blocks,
            'total_transactions': total_transactions,
            'latest_block': latest_block,
            'is_valid': BlockchainSimulator.validate_chain()
        }
    
    @staticmethod
    def get_user_transactions(user_id):
        """Get all blockchain transactions for a user"""
        blocks = Block.query.order_by(Block.index.desc()).all()
        user_transactions = []
        
        for block in blocks:
            transactions = block.get_transactions()
            for tx in transactions:
                if (tx.get('user_id') == user_id or 
                    tx.get('from_user_id') == user_id or 
                    tx.get('to_user_id') == user_id):
                    user_transactions.append({
                        'block_index': block.index,
                        'block_hash': block.hash,
                        'timestamp': block.timestamp,
                        'transaction': tx
                    })
        
        return user_transactions
    
    @staticmethod
    def initialize_genesis_block():
        """Initialize the blockchain with a genesis block"""
        if Block.query.count() == 0:
            genesis_transactions = [{
                'type': 'genesis',
                'message': 'Green Hydrogen Platform Genesis Block',
                'timestamp': datetime.utcnow().isoformat()
            }]
            
            BlockchainSimulator.add_block(genesis_transactions, 'system')
            print("Genesis block created")
