import secrets
import hashlib
import json
from datetime import datetime
from app import db
from models import SmartContract, Certificate
from blockchain import BlockchainSimulator

class SmartContractManager:
    
    @staticmethod
    def deploy_contract(contract_type, deployment_data, deployer_address=None):
        """Deploy a new smart contract"""
        address = f"0x{secrets.token_hex(20)}"
        code_hash = hashlib.sha256(json.dumps(deployment_data).encode()).hexdigest()
        
        contract = SmartContract(
            address=address,
            contract_type=contract_type,
            code_hash=code_hash
        )
        
        meta_data = {
            'deployer': deployer_address or f"deployer_{secrets.token_hex(4)}",
            'deployment_data': deployment_data,
            'version': '1.0.0'
        }
        contract.set_meta(meta_data)
        
        db.session.add(contract)
        db.session.commit()
        
        # Add blockchain transaction for contract deployment
        transactions = [{
            'type': 'contract_deployment',
            'contract_address': address,
            'contract_type': contract_type,
            'deployer': deployer_address,
            'code_hash': code_hash,
            'timestamp': datetime.utcnow().isoformat()
        }]
        
        BlockchainSimulator.add_block(transactions)
        
        return contract
    
    @staticmethod
    def execute_contract(contract_address, function_name, parameters, caller_address=None):
        """Execute a smart contract function"""
        contract = SmartContract.query.filter_by(address=contract_address).first()
        if not contract:
            return False, "Contract not found"
        
        if contract.status != 'active':
            return False, "Contract is not active"
        
        # Simulate contract execution based on type and function
        if contract.contract_type == 'certificate_validator':
            return SmartContractManager._execute_certificate_validator(contract, function_name, parameters, caller_address)
        elif contract.contract_type == 'carbon_credit_manager':
            return SmartContractManager._execute_carbon_credit_manager(contract, function_name, parameters, caller_address)
        elif contract.contract_type == 'marketplace_escrow':
            return SmartContractManager._execute_marketplace_escrow(contract, function_name, parameters, caller_address)
        
        return False, "Unknown contract type"
    
    @staticmethod
    def _execute_certificate_validator(contract, function_name, parameters, caller_address):
        """Execute certificate validator contract functions"""
        if function_name == 'validate_certificate':
            certificate_id = parameters.get('certificate_id')
            certificate = Certificate.query.filter_by(certificate_id=certificate_id).first()
            
            if not certificate:
                return False, "Certificate not found"
            
            # Simulate validation logic
            meta = certificate.get_meta()
            production_method = meta.get('production_method', '')
            carbon_intensity = meta.get('carbon_intensity', 0)
            
            # Green hydrogen validation criteria
            is_valid = (
                production_method in ['electrolysis_renewable', 'biomass_gasification'] and
                carbon_intensity <= 2.0  # kg CO2/kg H2
            )
            
            if is_valid:
                certificate.verification_status = 'verified'
                certificate.smart_contract_address = contract.address
            else:
                certificate.verification_status = 'rejected'
            
            db.session.commit()
            
            # Add blockchain transaction
            transactions = [{
                'type': 'certificate_validation',
                'contract_address': contract.address,
                'certificate_id': certificate_id,
                'validation_result': 'verified' if is_valid else 'rejected',
                'validator': caller_address,
                'timestamp': datetime.utcnow().isoformat()
            }]
            
            BlockchainSimulator.add_block(transactions)
            
            return True, f"Certificate {certificate_id} validation: {'verified' if is_valid else 'rejected'}"
        
        return False, "Unknown function"
    
    @staticmethod
    def _execute_carbon_credit_manager(contract, function_name, parameters, caller_address):
        """Execute carbon credit manager contract functions"""
        if function_name == 'calculate_credits':
            hydrogen_amount = parameters.get('hydrogen_amount', 0)
            production_method = parameters.get('production_method', '')
            
            # Calculate carbon credits based on hydrogen production
            credit_multiplier = {
                'electrolysis_renewable': 1.5,
                'biomass_gasification': 1.2,
                'steam_reforming_ccs': 0.8,
                'steam_reforming': 0.0
            }
            
            base_credits = hydrogen_amount * 0.1  # Base: 0.1 credit per kg H2
            multiplier = credit_multiplier.get(production_method, 0)
            total_credits = base_credits * multiplier
            
            result = {
                'hydrogen_amount': hydrogen_amount,
                'production_method': production_method,
                'calculated_credits': round(total_credits, 2),
                'multiplier': multiplier
            }
            
            # Add blockchain transaction
            transactions = [{
                'type': 'credit_calculation',
                'contract_address': contract.address,
                'result': result,
                'calculator': caller_address,
                'timestamp': datetime.utcnow().isoformat()
            }]
            
            BlockchainSimulator.add_block(transactions)
            
            return True, result
        
        return False, "Unknown function"
    
    @staticmethod
    def _execute_marketplace_escrow(contract, function_name, parameters, caller_address):
        """Execute marketplace escrow contract functions"""
        if function_name == 'create_escrow':
            trade_id = parameters.get('trade_id')
            amount = parameters.get('amount', 0)
            buyer = parameters.get('buyer')
            seller = parameters.get('seller')
            
            # Simulate escrow creation
            escrow_data = {
                'trade_id': trade_id,
                'amount': amount,
                'buyer': buyer,
                'seller': seller,
                'status': 'locked',
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Add blockchain transaction
            transactions = [{
                'type': 'escrow_created',
                'contract_address': contract.address,
                'escrow_data': escrow_data,
                'initiator': caller_address,
                'timestamp': datetime.utcnow().isoformat()
            }]
            
            BlockchainSimulator.add_block(transactions)
            
            return True, f"Escrow created for trade {trade_id}"
        
        elif function_name == 'release_escrow':
            trade_id = parameters.get('trade_id')
            
            # Add blockchain transaction
            transactions = [{
                'type': 'escrow_released',
                'contract_address': contract.address,
                'trade_id': trade_id,
                'releaser': caller_address,
                'timestamp': datetime.utcnow().isoformat()
            }]
            
            BlockchainSimulator.add_block(transactions)
            
            return True, f"Escrow released for trade {trade_id}"
        
        return False, "Unknown function"
    
    @staticmethod
    def get_contract_stats():
        """Get smart contract statistics"""
        total_contracts = SmartContract.query.count()
        active_contracts = SmartContract.query.filter_by(status='active').count()
        
        contracts_by_type = {}
        all_contracts = SmartContract.query.all()
        for contract in all_contracts:
            contract_type = contract.contract_type
            if contract_type not in contracts_by_type:
                contracts_by_type[contract_type] = 0
            contracts_by_type[contract_type] += 1
        
        return {
            'total_contracts': total_contracts,
            'active_contracts': active_contracts,
            'contracts_by_type': contracts_by_type
        }
    
    @staticmethod
    def auto_deploy_system_contracts():
        """Automatically deploy essential system contracts"""
        # Deploy certificate validator contract
        cert_validator = SmartContract.query.filter_by(contract_type='certificate_validator').first()
        if not cert_validator:
            SmartContractManager.deploy_contract(
                'certificate_validator',
                {
                    'name': 'Green Hydrogen Certificate Validator',
                    'description': 'Validates green hydrogen production certificates',
                    'validation_criteria': {
                        'max_carbon_intensity': 2.0,
                        'approved_methods': ['electrolysis_renewable', 'biomass_gasification']
                    }
                },
                'system'
            )
        
        # Deploy carbon credit manager contract
        credit_manager = SmartContract.query.filter_by(contract_type='carbon_credit_manager').first()
        if not credit_manager:
            SmartContractManager.deploy_contract(
                'carbon_credit_manager',
                {
                    'name': 'Carbon Credit Calculator',
                    'description': 'Calculates carbon credits for hydrogen production',
                    'credit_rates': {
                        'electrolysis_renewable': 1.5,
                        'biomass_gasification': 1.2,
                        'steam_reforming_ccs': 0.8
                    }
                },
                'system'
            )
        
        # Deploy marketplace escrow contract
        escrow_contract = SmartContract.query.filter_by(contract_type='marketplace_escrow').first()
        if not escrow_contract:
            SmartContractManager.deploy_contract(
                'marketplace_escrow',
                {
                    'name': 'Marketplace Escrow Service',
                    'description': 'Manages escrow for carbon credit trades',
                    'escrow_fee': 0.01  # 1% fee
                },
                'system'
            )
