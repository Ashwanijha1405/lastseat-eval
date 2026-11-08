def transfer(db, from_id: int, to_id: int, amount: int) -> bool:
    # Determine lock order: always lock the account with the smaller id first.
    # This prevents deadlocks because every transaction acquires locks in the same order.
    if from_id < to_id:
        low_id, low_is_sender = from_id, True
        high_id, high_is_sender = to_id, False
    else:
        low_id, low_is_sender = to_id, False
        high_id, high_is_sender = from_id, True

    # Start a transaction (default isolation is "read committed")
    db.begin()

    # Lock the lower‑id account first
    low_row = db.execute("SELECT balance FROM accounts WHERE id = %s FOR UPDATE", (low_id,))
    if not low_row:                     # should never happen because accounts always exist
        db.rollback()
        return False
    low_balance = low_row[0][0]

    # Lock the higher‑id account
    high_row = db.execute("SELECT balance FROM accounts WHERE id = %s FOR UPDATE", (high_id,))
    if not high_row:
        db.rollback()
        return False
    high_balance = high_row[0][0]

    # Identify sender and receiver based on which id corresponds to the sender
    if low_is_sender:
        sender_balance = low_balance
        receiver_balance = high_balance
    else:
        sender_balance = high_balance
        receiver_balance = low_balance

    # Check if the sender has enough funds
    if sender_balance < amount:
        db.rollback()
        return False

    # Perform the transfer: subtract from sender, add to receiver
    if low_is_sender:
        db.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, low_id))
        db.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, high_id))
    else:
        db.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, high_id))
        db.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, low_id))

    db.commit()
    return True
