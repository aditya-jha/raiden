# -*- coding: utf-8 -*-
from ethereum.utils import encode_hex

from raiden.transfer.architecture import State
from raiden.utils import typing
from raiden.transfer.state import (
    EMPTY_MERKLE_ROOT,
    BalanceProofState,
    BalanceProofUnsignedState,
    HashTimeLockState,
)
# pylint: disable=too-few-public-methods,too-many-arguments,too-many-instance-attributes


def lockedtransfer_from_message(message):
    """ Create LockedTransferState from a MediatedTransfer message. """
    transfer_state = LockedTransferState(
        identifier=message.identifier,
        amount=message.lock.amount,
        token=message.token,
        initiator=message.initiator,
        target=message.target,
        expiration=message.lock.expiration,
        hashlock=message.lock.hashlock,
        secret=None,
    )

    return transfer_state


class InitiatorState(State):
    """ State of a node initiating a mediated transfer.

    Args:
        our_address (address): This node address.
        transfer (LockedTransferState): The description of the mediated transfer.
        routes (RoutesState): Routes available for this transfer.
        block_number (int): Latest known block number.
        random_generator (generator): A generator that yields valid secrets.
    """
    __slots__ = (
        'our_address',
        'transfer',
        'routes',
        'block_number',
        'random_generator',
        'message',
        'route',
        'secretrequest',
        'revealsecret',
        'canceled_transfers',
    )

    def __init__(self, our_address, transfer, routes, block_number, random_generator):
        self.our_address = our_address
        self.transfer = transfer
        self.routes = routes
        self.block_number = block_number
        self.random_generator = random_generator

        self.message = None  #: current message in-transit
        self.route = None  #: current route being used
        self.secretrequest = None
        self.revealsecret = None
        self.canceled_transfers = list()

    def __eq__(self, other):
        if isinstance(other, InitiatorState):
            return (
                self.our_address == other.our_address and
                self.transfer == other.transfer and
                self.routes == other.routes and
                self.random_generator == other.random_generator and
                self.block_number == other.block_number and
                self.message == other.message and
                self.route == other.route and
                self.secretrequest == other.secretrequest and
                self.revealsecret == other.revealsecret and
                self.canceled_transfers == other.canceled_transfers
            )
        return False

    def __ne__(self, other):
        return not self.__eq__(other)


class MediatorState(State):
    """ State of a node mediating a transfer.

    Args:
        our_address (address): This node address.
        routes (RoutesState): Routes available for this transfer.
        block_number (int): Latest known block number.
        hashlock (bin): The hashlock used for this transfer.
    """
    __slots__ = (
        'our_address',
        'routes',
        'block_number',
        'hashlock',
        'secret',
        'transfers_pair',
    )

    def __init__(
            self,
            our_address,
            routes,
            block_number,
            hashlock):

        self.our_address = our_address
        self.routes = routes
        self.block_number = block_number

        # for convenience
        self.hashlock = hashlock
        self.secret = None

        # keeping all transfers in a single list byzantine behavior for secret
        # reveal and simplifies secret setting
        self.transfers_pair = list()

    def __eq__(self, other):
        if isinstance(other, MediatorState):
            return (
                self.our_address == other.our_address and
                self.routes == other.routes and
                self.block_number == other.block_number and
                self.hashlock == other.hashlock and
                self.secret == other.secret and
                self.transfers_pair == other.transfers_pair
            )
        return False

    def __ne__(self, other):
        return not self.__eq__(other)


class TargetState(State):
    """ State of mediated transfer target.  """
    __slots__ = (
        'our_address',
        'from_route',
        'from_transfer',
        'block_number',
        'secret',
        'state',
    )

    valid_states = (
        'secret_request',
        'reveal_secret',
        'balance_proof',
        'waiting_close',
    )

    def __init__(
            self,
            our_address,
            from_route,
            from_transfer,
            block_number):

        self.our_address = our_address
        self.from_route = from_route
        self.from_transfer = from_transfer
        self.block_number = block_number

        self.secret = None
        self.state = 'secret_request'

    def __eq__(self, other):
        if isinstance(other, TargetState):
            return (
                self.our_address == other.our_address and
                self.from_route == other.from_route and
                self.from_transfer == other.from_transfer and
                self.block_number == other.block_number and
                self.secret == other.secret and
                self.state == other.state
            )

        return False

    def __ne__(self, other):
        return not self.__eq__(other)


class LockedTransferUnsignedState(State):
    """ State for a transfer created by the local node which contains a hash
    time lock and may be sent.
    """

    __slots__ = (
        'identifier',
        'token',
        'balance_proof',
        'lock',
        'initiator',
        'target',
    )

    def __init__(
            self,
            identifier,
            token: typing.address,
            balance_proof: BalanceProofUnsignedState,
            lock: HashTimeLockState,
            initiator: typing.address,
            target: typing.address):

        if not isinstance(lock, HashTimeLockState):
            raise ValueError('lock must be a HashTimeLockState instance')

        if not isinstance(balance_proof, BalanceProofUnsignedState):
            raise ValueError('balance_proof must be a BalanceProofState instance')

        # At least the lock for this transfer must be in the locksroot, so it
        # must not be empty
        if balance_proof.locksroot is EMPTY_MERKLE_ROOT:
            raise ValueError('balance_proof must not be empty')

        self.identifier = identifier
        self.token = token
        self.balance_proof = balance_proof
        self.lock = lock
        self.initiator = initiator
        self.target = target

    def __repr__(self):
        return (
            '<LockedTransferUnsignedState id:{} token:{} lock:{} target:{}>'
        ).format(
            self.identifier,
            encode_hex(self.token),
            self.lock,
            encode_hex(self.target),
        )

    def __eq__(self, other):
        return (
            isinstance(other, LockedTransferUnsignedState) and
            self.identifier == other.identifier and
            self.token == other.token and
            self.balance_proof == other.balance_proof and
            self.lock == other.lock and
            self.initiator == other.initiator and
            self.target == other.target
        )

    def __ne__(self, other):
        return not self.__eq__(other)


class LockedTransferSignedState(State):
    """ State for a received transfer which contains a hash time lock and a
    signed balance proof.
    """

    __slots__ = (
        'identifier',
        'token',
        'balance_proof',
        'lock',
        'initiator',
        'target',
    )

    def __init__(
            self,
            identifier,
            token: typing.address,
            balance_proof: BalanceProofState,
            lock: HashTimeLockState,
            initiator: typing.address,
            target: typing.address):

        if not isinstance(lock, HashTimeLockState):
            raise ValueError('lock must be a HashTimeLockState instance')

        if not isinstance(balance_proof, BalanceProofState):
            raise ValueError('balance_proof must be a BalanceProofState instance')

        # At least the lock for this transfer must be in the locksroot, so it
        # must not be empty
        if balance_proof.locksroot is EMPTY_MERKLE_ROOT:
            raise ValueError('balance_proof must not be empty')

        self.identifier = identifier
        self.token = token
        self.balance_proof = balance_proof
        self.lock = lock
        self.initiator = initiator
        self.target = target

    def __repr__(self):
        return (
            '<LockedTransferState id:{} token:{} lock:{} target:{}>'
        ).format(
            self.identifier,
            encode_hex(self.token),
            self.lock,
            encode_hex(self.target),
        )

    def __eq__(self, other):
        return (
            isinstance(other, LockedTransferState) and
            self.identifier == other.identifier and
            self.token == other.token and
            self.balance_proof == other.balance_proof and
            self.lock == other.lock and
            self.initiator == other.initiator and
            self.target == other.target
        )

    def __ne__(self, other):
        return not self.__eq__(other)


class LockedTransferState(State):
    """ State of a transfer that is time hash locked.

    Args:
        identifier (int): A unique identifer for the transfer.
        amount (int): Amount of `token` being transferred.
        token (address): Token being transferred.
        target (address): Transfer target address.
        expiration (int): The absolute block number that the lock expires.
        hashlock (bin): The hashlock.
        secret (bin): The secret that unlocks the lock, may be None.
    """
    __slots__ = (
        'identifier',
        'amount',
        'token',
        'initiator',
        'target',
        'expiration',
        'hashlock',
        'secret',
    )

    def __init__(
            self,
            identifier,
            amount,
            token,
            initiator,
            target,
            expiration,
            hashlock,
            secret):

        self.identifier = identifier
        self.amount = amount
        self.token = token
        self.initiator = initiator
        self.target = target
        self.expiration = expiration
        self.hashlock = hashlock
        self.secret = secret

    def __repr__(self):
        return '<HashTimeLocked id={} amount={} token={} target={} expire={} hashlock={}>'.format(
            self.identifier,
            self.amount,
            encode_hex(self.token),
            encode_hex(self.target),
            self.expiration,
            encode_hex(self.hashlock),
        )

    def almost_equal(self, other):
        """ True if both transfers are for the same mediated transfer. """
        if isinstance(other, LockedTransferState):
            # the only value that may change for each hop is the expiration
            return (
                self.identifier == other.identifier and
                self.amount == other.amount and
                self.token == other.token and
                self.target == other.target and
                self.hashlock == other.hashlock and
                self.secret == other.secret
            )

    def __eq__(self, other):
        if isinstance(other, LockedTransferState):
            return (
                self.almost_equal(other) and
                self.expiration == other.expiration
            )

        return False

    def __ne__(self, other):
        return not self.__eq__(other)


class MediationPairState(State):
    """ State for a mediated transfer.

    A mediator will pay payee node knowing that there is a payer node to cover
    the token expenses. This state keeps track of the routes and transfer for
    the payer and payee, and the current state of the payment.
    """
    __slots__ = (
        'payee_route',
        'payee_transfer',
        'payee_state',

        'payer_route',
        'payer_transfer',
        'payer_state',
    )

    # payee_pending:
    #   Initial state.
    #
    # payee_secret_revealed:
    #   The payee is following the raiden protocol and has sent a SecretReveal.
    #
    # payee_refund_withdraw:
    #   The corresponding refund transfer was withdrawn on-chain, the payee has
    #   /not/ withdrawn the lock yet, it only learned the secret through the
    #   blockchain.
    #   Note: This state is reachable only if there is a refund transfer, that
    #   is represented by a different MediationPairState, and the refund
    #   transfer is at 'payer_contract_withdraw'.
    #
    # payee_contract_withdraw:
    #   The payee received the token on-chain. A transition to this state is
    #   valid from all but the `payee_expired` state.
    #
    # payee_balance_proof:
    #   This node has sent a SendBalanceProof to the payee with the balance
    #   updated.
    #
    # payee_expired:
    #   The lock has expired.
    valid_payee_states = (
        'payee_pending',
        'payee_secret_revealed',
        'payee_refund_withdraw',
        'payee_contract_withdraw',
        'payee_balance_proof',
        'payee_expired',
    )

    valid_payer_states = (
        'payer_pending',
        'payer_secret_revealed',    # SendRevealSecret was sent
        'payer_waiting_close',      # ContractSendChannelClose was sent
        'payer_waiting_withdraw',   # ContractSendWithdraw was sent
        'payer_contract_withdraw',  # ContractReceiveWithdraw for the above send received
        'payer_balance_proof',      # ReceiveBalanceProof was received
        'payer_expired',            # None of the above happened and the lock expired
    )

    def __init__(
            self,
            payer_route,
            payer_transfer,
            payee_route,
            payee_transfer):
        """
        Args:
            payer_route (RouteState): The details of the route with the payer.
            payer_transfer (LockedTransferState): The transfer this node
                *received* that will cover the expenses.

            payee_route (RouteState): The details of the route with the payee.
            payee_transfer (LockedTransferState): The transfer this node *sent*
                that will be withdrawn by the payee.
        """
        self.payer_route = payer_route
        self.payer_transfer = payer_transfer

        self.payee_route = payee_route
        self.payee_transfer = payee_transfer

        # these transfers are settled on different payment channels. These are
        # the states of each mediated transfer in respect to each channel.
        self.payer_state = 'payer_pending'
        self.payee_state = 'payee_pending'

    def __eq__(self, other):
        if isinstance(other, MediationPairState):
            return (
                self.payee_route == other.payee_route and
                self.payee_transfer == other.payee_transfer and
                self.payee_state == other.payee_state and

                self.payer_route == other.payer_route and
                self.payer_transfer == other.payer_transfer and
                self.payer_state == other.payer_state
            )
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return (
            '<MediationPairState payer_route:{payer_route} payer_transfer:{payer_transfer} '
            'payer_state:{payer_state} payee_route:{payee_route} '
            'payee_transfer:{payee_transfer} payee_state:{payee_state}>'
        ).format(
            payer_route=self.payer_route,
            payer_transfer=self.payer_transfer,
            payer_state=self.payer_state,
            payee_route=self.payee_route,
            payee_transfer=self.payee_transfer,
            payee_state=self.payee_state
        )
