# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2019 grandizzy
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import logging
import time
from math import sqrt
from typing import List, Dict

from attrdict import AttrDict
from web3 import Web3

from pymaker import Contract, Address, Transact, Wad
from pymaker.token import ERC20Token


class MooniFactory(Contract):
    abi = Contract._load_abi(__name__, 'abi/MooniFactory.abi')

    def __init__(self, web3: Web3, factory_address: Address):
        assert (isinstance(web3, Web3))
        assert (isinstance(factory_address, Address))

        self.web3 = web3
        self.address = factory_address
        self._contract = self._get_contract(web3, self.abi, factory_address)

    def get_pair_address(self, first_token: Address, second_token: Address) -> Address:
        return Address(self._contract.functions.pools(first_token.address, second_token.address).call())

    def get_pairs_addreses(self) -> List[Address]:
        return list(map(Address, self._contract.functions.getAllPools().call()))

    def get_pair(self, first_token: Address, second_token: Address) -> 'Mooniswap':
        return Mooniswap(web3=self.web3, pair_address=self.get_pair_address(first_token=first_token,
                                                                            second_token=second_token))

    def create_pair(self, first_token: Address, second_token: Address) -> Transact:
        return Transact(self, self.web3, self.abi, self.address, self._contract,
                        'deploy', [first_token.address, second_token.address])

    def __eq__(self, other):
        assert(isinstance(other, MooniFactory))
        return self.address == other.address

    def __repr__(self):
        return f"MooniFactory('{self.address}')"


class Mooniswap(Contract):
    abi = Contract._load_abi(__name__, 'abi/Mooniswap.abi')

    def __init__(self, web3: Web3, pair_address: Address):
        assert (isinstance(web3, Web3))
        assert (isinstance(pair_address, Address))

        self.web3 = web3
        self.address = pair_address
        self._contract = self._get_contract(web3, self.abi, pair_address)
        self.account_address = Address(self.web3.eth.defaultAccount)

    @property
    def reserves(self) -> AttrDict:
        # _reserves = self._contract.functions.getReserves().call()
        tokens = [self.first_token.address, self.second_token.address]

        functions = list(map(self._contract.functions.getBalanceForRemoval, tokens))
        _reserves = [function.call() for function in functions]

        return AttrDict({
            'first_token': self.first_token,
            'first_token_amount': Wad(_reserves[0]),
            'second_token': self.second_token,
            'second_token_amount': Wad(_reserves[1]),

            'map': lambda: AttrDict({self.first_token: Wad(_reserves[0]), self.second_token: Wad(_reserves[1])})
        })

    @property
    def first_token(self) -> Address:
        return Address(self._contract.functions.tokens(0).call())

    @property
    def second_token(self) -> Address:
        return Address(self._contract.functions.tokens(1).call())

    @property
    def liquidity(self) -> Wad:
        return self.get_liquidity(self.account_address)

    def approve(self, tokens: List[ERC20Token], approval_function):
        """Approve the Uniswap contract to fully access balances of specified tokens.

        For available approval functions (i.e. approval modes) see `directly` and `via_tx_manager`
        in `pymaker.approval`.

        Args:
            tokens: List of :py:class:`pymaker.token.ERC20Token` class instances.
            approval_function: Approval function (i.e. approval mode).
        """
        assert(isinstance(tokens, list))
        assert(callable(approval_function))

        for token in tokens:
            approval_function(token, self.address, 'UniswapPair')

    def get_liquidity(self, address: Address) -> Wad:
        return Wad(self._contract.functions.balanceOf(address.address).call())

    def swap(self, src: Address, dst: Address, amount: Wad, min_return: Wad, referral: Address = None) -> Transact:
        referral = Address('0x0000000000000000000000000000000000000000') if referral is None else referral

        if src == Address('0x0000000000000000000000000000000000000000'):
            return Transact(self, self.web3, self.abi, self.address, self._contract, 'swap',
                            [src.address, dst.address, amount.value, min_return.value, referral.address, ],
                            {'value': amount.value})
        else:
            return Transact(self, self.web3, self.abi, self.address, self._contract, 'swap',
                            [src.address, dst.address, amount.value, min_return.value, referral.address, ])

    def deposit(self, fst_token_amount: Wad, fst_token_min_amount: Wad,
                scd_token_amount: Wad, scd_token_min_amount: Wad) -> Transact:

        if self.first_token == Address('0x0000000000000000000000000000000000000000'):
            return Transact(self, self.web3, self.abi, self.address, self._contract, 'deposit',
                            [[fst_token_amount.value, scd_token_amount.value],
                             [fst_token_min_amount.value, scd_token_min_amount.value]],
                            {'value': fst_token_amount.value})
        elif self.second_token == Address('0x0000000000000000000000000000000000000000'):
            return Transact(self, self.web3, self.abi, self.address, self._contract, 'deposit',
                            [[fst_token_amount.value, scd_token_amount.value],
                             [fst_token_min_amount.value, scd_token_min_amount.value]],
                            {'value': scd_token_amount.value})
        else:
            return Transact(self, self.web3, self.abi, self.address, self._contract, 'deposit',
                            [[fst_token_amount.value, scd_token_amount.value],
                             [fst_token_min_amount.value, scd_token_min_amount.value]])

    def withdraw(self, amount: Wad, fst_token_min_returns: Wad, scd_token_min_returns: Wad) -> Transact:
        return Transact(self, self.web3, self.abi, self.address, self._contract, 'withdraw',
                        [amount.value, [fst_token_min_returns.value, scd_token_min_returns.value]])

    def get_return(self, src: Address, dst: Address, amount: Wad) -> Wad:
        return Wad(self._contract.functions.getReturn(src.address, dst.address, amount.value).call())

    def __eq__(self, other):
        assert(isinstance(other, Mooniswap))
        return self.address == other.address

    def __repr__(self):
        return f"Mooniswap('{self.address}')"


class MarketMaker:
    mooniswap = None
    logger = logging.getLogger(__name__)

    def __init__(self, mooniswap: Mooniswap):
        assert (isinstance(mooniswap, Mooniswap))

        self.mooniswap = mooniswap

    @staticmethod
    def calculate_value(value: Wad, percent) -> Wad:
        """
        RU:
            Расчет цены с учетом процента наценки или скидки
        EN:
            Calculating the price with a percentage of the markup or discount
        example:
            calculate_value(100, 10):   100 + 10% = 110
            calculate_value(100, -10):  100 + (-10)% = 90
        """
        percent_value = Wad(value.value * percent / 100)
        return value.value + percent_value.value

    @staticmethod
    def _get_amounts(market_price: Wad, first_token: Address, second_token: Address, reserved: AttrDict) -> AttrDict:

        liquidity_pool_constant = reserved[first_token] * reserved[second_token]
        new_reserved = {
            first_token: Wad.from_number(sqrt(liquidity_pool_constant * market_price)),
            second_token: Wad.from_number(sqrt(liquidity_pool_constant / market_price)),
        }

        # new_first_token_liquidity_pool_amount = Wad.from_number(sqrt(liquidity_pool_constant * market_price))
        # new_second_token_liquidity_pool_amount = Wad.from_number(sqrt(liquidity_pool_constant / market_price))

        if new_reserved[first_token] > reserved[first_token]:
            first_token_delta_amount = new_reserved[first_token] - reserved[first_token]
            second_token_delta_amount = reserved[second_token] - new_reserved[second_token]
        else:
            first_token_delta_amount = reserved[first_token] - new_reserved[first_token]
            second_token_delta_amount = new_reserved[second_token] - reserved[second_token]

        return AttrDict({
            'first_token_amount_delta': first_token_delta_amount,
            'second_token_amount_delta': second_token_delta_amount,

            'map': lambda: AttrDict({first_token: first_token_delta_amount, second_token: second_token_delta_amount})
        })

    def set_price(self, market_price: Wad, first_token: Address, second_token: Address, max_delta_on_percent: int) -> Transact:

        reserves = self.mooniswap.reserves.map()

        mooniswap_price = reserves[first_token] / reserves[second_token]
        delta = (market_price.value * 100 / mooniswap_price.value) - 100

        self.logger.info(f"the price differs from the market by {delta}%")

        if delta > max_delta_on_percent:
            self.logger.debug(f"delta > max_delta ({delta} > {max_delta_on_percent})")
            input_data = self._get_amounts(market_price=market_price, first_token=first_token, second_token=second_token, reserved=reserves)

            min_amount = self.mooniswap.get_return(src=first_token, dst=second_token,
                                                   amount=input_data.map()[first_token])

            return self.mooniswap.swap(src=first_token, dst=second_token,
                                       amount=input_data.map()[first_token], min_return=min_amount, referral=None)

        elif delta < 0 and abs(delta) > max_delta_on_percent:
            self.logger.debug(f"delta < max_delta ({delta} < {max_delta_on_percent})")
            input_data = self._get_amounts(market_price=market_price, first_token=first_token, second_token=second_token, reserved=reserves)

            min_amount = self.mooniswap.get_return(src=second_token, dst=first_token,
                                                   amount=input_data.map()[second_token])

            return self.mooniswap.swap(src=second_token, dst=first_token,
                                       amount=input_data.map()[second_token], min_return=min_amount, referral=None)

        else:
            self.logger.info(f"the price difference is within "
                             f"the permissible (delta={delta}, max_delta={max_delta_on_percent})")
