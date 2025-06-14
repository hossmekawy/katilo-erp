#!/usr/bin/env python3
"""
Test script to verify supplier accounting logic
This script checks if payments are properly recorded in supplier ledgers
"""

from models import Supplier, SupplierLedgerEntry, SupplierPayment, CashAccount, CashTransferVoucher
from app import app
from datetime import datetime

def test_supplier_accounting():
    """Test supplier accounting logic"""
    
    with app.app_context():
        print("=== Supplier Accounting Test ===\n")
        
        # Get first supplier
        supplier = Supplier.query.first()
        if not supplier:
            print("❌ No suppliers found!")
            return
            
        print(f"Testing supplier: {supplier.supplier_name}")
        print("-" * 50)
        
        # Get all ledger entries for this supplier
        ledger_entries = SupplierLedgerEntry.query.filter_by(
            supplier_id=supplier.id
        ).order_by(SupplierLedgerEntry.entry_date.desc()).all()
        
        print(f"Total ledger entries: {len(ledger_entries)}")
        
        # Calculate balance
        total_debit = 0  # What we owe to supplier
        total_credit = 0  # What we've paid to supplier
        
        print("\nLedger Entries:")
        print("Date\t\tType\t\tDescription\t\tDebit\tCredit")
        print("-" * 80)
        
        for entry in ledger_entries:
            total_debit += entry.debit
            total_credit += entry.credit
            
            print(f"{entry.entry_date.strftime('%Y-%m-%d')}\t"
                  f"{entry.reference_type}\t"
                  f"{entry.description[:20]:<20}\t"
                  f"{entry.debit:.2f}\t{entry.credit:.2f}")
        
        balance = total_debit - total_credit
        
        print("-" * 80)
        print(f"Total Debit (Owed): {total_debit:.2f}")
        print(f"Total Credit (Paid): {total_credit:.2f}")
        print(f"Balance (Outstanding): {balance:.2f}")
        
        # Check recent payments
        print(f"\nRecent Payments:")
        payments = SupplierPayment.query.filter_by(
            supplier_id=supplier.id
        ).order_by(SupplierPayment.payment_date.desc()).limit(5).all()
        
        for payment in payments:
            print(f"  - {payment.payment_date.strftime('%Y-%m-%d')}: "
                  f"{payment.amount:.2f} ({payment.payment_method})")
        
        # Check recent cash transfers
        print(f"\nRecent Cash Transfers:")
        transfers = CashTransferVoucher.query.filter_by(
            supplier_id=supplier.id
        ).order_by(CashTransferVoucher.transfer_date.desc()).limit(5).all()
        
        for transfer in transfers:
            print(f"  - {transfer.transfer_date.strftime('%Y-%m-%d')}: "
                  f"{transfer.amount:.2f} (Voucher: {transfer.voucher_number})")
        
        # Verify consistency
        print(f"\nConsistency Check:")
        payment_total = sum(p.amount for p in payments)
        transfer_total = sum(t.amount for t in transfers)
        
        print(f"Total from SupplierPayment table: {payment_total:.2f}")
        print(f"Total from CashTransferVoucher table: {transfer_total:.2f}")
        print(f"Total credits in ledger: {total_credit:.2f}")
        
        if abs(total_credit - (payment_total + transfer_total)) < 0.01:
            print("✅ Accounting is consistent!")
        else:
            print("❌ Accounting inconsistency detected!")
            print(f"   Difference: {total_credit - (payment_total + transfer_total):.2f}")

def test_cash_account_balance():
    """Test cash account balances"""
    
    with app.app_context():
        print(f"\n=== Cash Account Balance Test ===\n")
        
        cash_accounts = CashAccount.query.filter_by(
            account_type='cash', 
            is_active=True
        ).limit(3).all()
        
        for account in cash_accounts:
            print(f"Account: {account.name}")
            print(f"Current Balance: {account.current_balance:.2f} {account.currency}")
            
            # Check if balance is sufficient for a test payment
            if account.current_balance > 100:
                print("✅ Sufficient balance for payments")
            else:
                print("⚠️  Low balance - may need replenishment")
            print()

if __name__ == "__main__":
    test_supplier_accounting()
    test_cash_account_balance()
