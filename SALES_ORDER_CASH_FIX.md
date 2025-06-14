# Sales Order Double-Counting Fix

## Problem Description

The Katilo ERP system was experiencing double-counting of revenue due to automatic cash booking when sales orders were created. This resulted in:

1. **Sales Order Creation**: Cash was automatically booked to Safe account when order was confirmed
2. **Invoice Payment**: Cash was booked again when actual payment was received

This created duplicate cash entries for the same sale.

## Root Cause Analysis

In `routes/sales_routes.py`, the `create_order()` function (lines 149-220) had logic that:

1. Set `payment_status = 'Paid'` if payment method was cash and cash account was provided
2. Automatically updated cash account balance: `cash_account.current_balance += order.total_amount`
3. Created a cash transaction with `reference_type='sales_order'`

This was incorrect because sales orders should not trigger cash movements - only actual payments should.

## Solution Implemented

### Changes Made to `routes/sales_routes.py`

**Before (Problematic Code):**
```python
# If payment method is cash and cash account is provided, set status to Paid
if payment_method == 'cash' and cash_account_id:
    payment_status = 'Paid'

# ... later in the function ...

# If payment is cash and cash account is provided, record the transaction
if payment_method == 'cash' and cash_account_id:
    # Get the cash account
    cash_account = CashAccount.query.get(cash_account_id)
    if cash_account:
        # Update the cash account balance
        cash_account.current_balance += order.total_amount

        # Create a cash transaction record
        transaction = CashTransaction(
            account_id=cash_account_id,
            transaction_type='deposit',
            amount=order.total_amount,
            reference_type='sales_order',
            reference_id=order.id,
            description=f"Sales payment for order #{order.id}",
            transaction_date=datetime.now(),
            created_by=current_user.id
        )
        db.session.add(transaction)
```

**After (Fixed Code):**
```python
# FIXED: Do not automatically set payment status to 'Paid' for sales orders
# Payment status should only be updated when actual payments are received through invoices
payment_status = 'Unpaid'

# ... later in the function ...

# FIXED: Remove automatic cash booking for sales orders
# Cash should only be booked when invoices are paid, not when orders are created
# This prevents double-counting of revenue
```

### What the Fix Does

1. **Removes automatic cash booking**: Sales orders no longer create cash transactions
2. **Sets correct payment status**: All new orders start with `payment_status = 'Unpaid'`
3. **Preserves payment information**: Payment method and cash account are still stored for reference
4. **Maintains invoice payment process**: The correct cash booking happens when invoices are paid

### Invoice Payment Process (Unchanged)

The invoice payment process in `process_payment()` function (lines 581-675) remains correct and handles cash booking properly:

```python
# If payment method is cash and cash account is provided, record the transaction
if payment_method.lower() == 'cash' and cash_account_id:
    # Get the cash account
    cash_account = CashAccount.query.get(cash_account_id)
    if cash_account:
        # Update the cash account balance
        cash_account.current_balance += amount

        # Create a cash transaction record
        transaction = CashTransaction(
            account_id=cash_account_id,
            transaction_type='deposit',
            amount=amount,
            reference_type='sales_payment',  # Correct reference type
            reference_id=payment.id,
            description=f"Payment for invoice #{invoice.invoice_number}",
            transaction_date=datetime.now(),
            created_by=current_user.id
        )
        db.session.add(transaction)
```

## Business Logic Flow (After Fix)

### Correct Flow:
1. **Sales Order Creation** → No cash movement, `payment_status = 'Unpaid'`
2. **Invoice Creation** → Links to sales order, `status = 'Unpaid'`
3. **Invoice Payment** → Cash is booked to Safe account, `status = 'Paid'`

### Result:
- Cash is recorded exactly once when actual payment is received
- No double-counting of revenue
- Proper audit trail with correct reference types

## Files Modified

- `routes/sales_routes.py` - Lines 149-202 (create_order function)

## Testing Recommendations

1. Create a new sales order with cash payment method
2. Verify no cash transaction is created at order confirmation
3. Create an invoice for the order
4. Process payment for the invoice
5. Verify cash transaction is created only once with correct amount

## Impact

- **Positive**: Eliminates double-counting of revenue
- **Positive**: Maintains proper accounting separation between orders and payments
- **Neutral**: No impact on existing functionality
- **Neutral**: Payment information is still captured for reference
