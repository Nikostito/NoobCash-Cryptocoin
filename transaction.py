from collections import OrderedDict

from utility.printable import Printable
from utility.hash_util import hash_transaction
from block import Block

class Transaction(Printable):
    """A transaction which can be added to a block in the blockchain.

    Attributes:
        :sender: The sender of the coins.
        :recipient: The recipient of the coins.
        :signature: The signature of the transaction.
        :amount: The amount of coins sent.
    """

    def __init__(self, sender, recipient, signature, amount, tx_sender, tx_recipient, id):
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.signature = signature
        self.tx_sender = tx_sender
        self.tx_recipient = tx_recipient
        self.id = hash_transaction(self)

    def to_ordered_dict(self):
        """Converts this transaction into a (hashable) OrderedDict."""
        return OrderedDict([('sender', self.sender),
                            ('recipient', self.recipient),
                            ('amount', self.amount)])
