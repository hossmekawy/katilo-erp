from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum, CheckConstraint
import enum

# Import db from main models file
from models import db, User, Supplier

# Enum for transaction types
class CashTransactionType(enum.Enum):
    CASH_IN = "cash_in"
    CASH_OUT = "cash_out"
    TRANSFER = "transfer"
    ADJUSTMENT = "adjustment"

# Enum for transaction status
class CashTransactionStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RECONCILED = "reconciled"

# Cash Balance Model
class CashBalance(db.Model):
    __tablename__ = 'cash_balances'
    id = db.Column(db.Integer, primary_key=True)
    account_name = db.Column(db.String(100), nullable=False)
    current_balance = db.Column(db.Float, default=0.0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    transactions = db.relationship('CashTransaction', backref='cash_account', lazy=True, 
                                  foreign_keys='CashTransaction.account_id')
    creator = db.relationship('User', backref='created_cash_accounts', lazy=True,
                             foreign_keys=[created_by])
    
    __table_args__ = (
        CheckConstraint('current_balance >= 0', name='check_positive_balance'),
    )
    
    def __repr__(self):
        return f"<CashBalance {self.account_name}: {self.current_balance}>"

# Cash Transaction Model
class CashTransaction(db.Model):
    __tablename__ = 'cash_transactions'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('cash_balances.id'), nullable=False)
    transaction_type = db.Column(Enum(CashTransactionType), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    reference_type = db.Column(db.String(50))  # 'supplier_payment', 'sales_receipt', etc.
    reference_id = db.Column(db.Integer)
    status = db.Column(Enum(CashTransactionStatus), default=CashTransactionStatus.PENDING)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    
    # Relationships
    creator = db.relationship('User', backref='created_cash_transactions', lazy=True,
                             foreign_keys=[created_by])
    approver = db.relationship('User', backref='approved_cash_transactions', lazy=True,
                              foreign_keys=[approved_by])
    
    # For transfers
    transfer_voucher_id = db.Column(db.Integer, db.ForeignKey('cash_transfer_vouchers.id'))
    
    __table_args__ = (
        CheckConstraint('amount > 0', name='check_positive_amount'),
    )
    
    def __repr__(self):
        return f"<CashTransaction {self.id}: {self.transaction_type.value} {self.amount}>"

# Cash Transfer Voucher Model
class CashTransferVoucher(db.Model):
    __tablename__ = 'cash_transfer_vouchers'
    id = db.Column(db.Integer, primary_key=True)
    voucher_number = db.Column(db.String(50), unique=True)
    source_account_id = db.Column(db.Integer, db.ForeignKey('cash_balances.id'), nullable=False)
    destination_account_id = db.Column(db.Integer, db.ForeignKey('cash_balances.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transfer_date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    status = db.Column(Enum(CashTransactionStatus), default=CashTransactionStatus.PENDING)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    
    # Relationships
    source_account = db.relationship('CashBalance', backref='outgoing_transfers', lazy=True,
                                    foreign_keys=[source_account_id])
    destination_account = db.relationship('CashBalance', backref='incoming_transfers', lazy=True,
                                         foreign_keys=[destination_account_id])
    creator = db.relationship('User', backref='created_transfer_vouchers', lazy=True,
                             foreign_keys=[created_by])
    approver = db.relationship('User', backref='approved_transfer_vouchers', lazy=True,
                              foreign_keys=[approved_by])
    transactions = db.relationship('CashTransaction', backref='transfer_voucher', lazy=True)
    
    __table_args__ = (
        CheckConstraint('amount > 0', name='check_positive_transfer_amount'),
        CheckConstraint('source_account_id != destination_account_id', name='check_different_accounts'),
    )
    
    def __repr__(self):
        return f"<CashTransferVoucher {self.voucher_number}: {self.amount}>"

# Cash Reconciliation Model
class CashReconciliation(db.Model):
    __tablename__ = 'cash_reconciliations'
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('cash_balances.id'), nullable=False)
    reconciliation_date = db.Column(db.DateTime, default=datetime.utcnow)
    system_balance = db.Column(db.Float, nullable=False)
    actual_balance = db.Column(db.Float, nullable=False)
    difference = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(Enum(CashTransactionStatus), default=CashTransactionStatus.PENDING)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    
    # Relationships
    account = db.relationship('CashBalance', backref='reconciliations', lazy=True)
    creator = db.relationship('User', backref='created_reconciliations', lazy=True,
                             foreign_keys=[created_by])
    approver = db.relationship('User', backref='approved_reconciliations', lazy=True,
                              foreign_keys=[approved_by])
    
    def __repr__(self):
        return f"<CashReconciliation {self.id}: {self.account.account_name} Diff: {self.difference}>"

# Supplier Cash Link Model (to connect suppliers with cash transactions)
class SupplierCashLink(db.Model):
    __tablename__ = 'supplier_cash_links'
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.SupplierID'), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('cash_transactions.id'), nullable=False)
    
    # Relationships
    supplier = db.relationship('Supplier', backref='cash_transactions', lazy=True)
    transaction = db.relationship('CashTransaction', backref='supplier_links', lazy=True)
    
    def __repr__(self):
        return f"<SupplierCashLink Supplier: {self.supplier_id} Transaction: {self.transaction_id}>"
