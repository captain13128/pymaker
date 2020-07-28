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

import time
from math import sqrt
from typing import List, Dict

from attrdict import AttrDict
from web3 import Web3

from pymaker import Contract, Address, Transact, Wad
from pymaker.token import ERC20Token


class UniswapFactory(Contract):
    abi = Contract._load_abi(__name__, 'abi/UniswapV2Factory.abi')

    def __init__(self, web3: Web3, factory_address: Address):
        assert (isinstance(web3, Web3))
        assert (isinstance(factory_address, Address))

        self.web3 = web3
        self.address = factory_address
        self._contract = self._get_contract(web3, self.abi, factory_address)

    def get_pair_address(self, first_token: Address, second_token: Address) -> Address:
        return Address(self._contract.functions.getPair(first_token.address, second_token.address).call())

    def get_pairs_addreses(self) -> List[Address]:
        all_pairs_length = self._contract.functions.allPairsLength().call()
        return [Address(self._contract.functions.allPairs(address_index).call()) for address_index in range(all_pairs_length)]

    def create_pair(self, first_token: Address, second_token: Address) -> Transact:
        return Transact(self, self.web3, self.abi, self.address, self._contract,
                        'createPair', [first_token.address, second_token.address])

    def __eq__(self, other):
        assert(isinstance(other, UniswapFactory))
        return self.address == other.address

    def __repr__(self):
        return f"UniswapFactory('{self.address}')"


class UniswapPair(Contract):
    abi = Contract._load_abi(__name__, 'abi/UniswapV2Pair.abi')

    def __init__(self, web3: Web3, pair_address: Address):
        assert (isinstance(web3, Web3))
        assert (isinstance(pair_address, Address))

        self.web3 = web3
        self.address = pair_address
        self._contract = self._get_contract(web3, self.abi, pair_address)
        self.account_address = Address(self.web3.eth.defaultAccount)

    @property
    def reserves(self) -> AttrDict:
        _reserves = self._contract.functions.getReserves().call()
        return AttrDict({
            'first_token': self.first_token,
            'first_token_amount': Wad(_reserves[0]),
            'second_token': self.second_token,
            'second_token_amount': Wad(_reserves[1]),

            'map': lambda: AttrDict({self.first_token: Wad(_reserves[0]), self.second_token: Wad(_reserves[1])})
        })

    @property
    def first_token(self) -> Address:
        return Address(self._contract.functions.token0().call())

    @property
    def second_token(self) -> Address:
        return Address(self._contract.functions.token1().call())

    @property
    def liquidity(self) -> Wad:
        return self.get_liquidity(self.account_address.address)

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

    def __eq__(self, other):
        assert(isinstance(other, UniswapPair))
        return self.address == other.address

    def __repr__(self):
        return f"UniswapPair('{self.address}')"


class UniswapRouter(Contract):
    abi = Contract._load_abi(__name__, 'abi/UniswapV2Router02.abi')
    zero_address = Address('0x0000000000000000000000000000000000000000')

    def __init__(self, web3: Web3, router: Address):
        assert(isinstance(web3, Web3))
        assert(isinstance(router, Address))

        self.web3 = web3
        self.address = router
        self._contract = self._get_contract(web3, self.abi, router)
        self.account_address = Address(self.web3.eth.defaultAccount)

    @property
    def factory(self) -> UniswapFactory:
        return UniswapFactory(web3=self.web3, factory_address=self.get_factory_address())

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
            approval_function(token, self.address, 'UniswapRouter')

    def get_pair(self, first_token: Address, second_token: Address) -> UniswapPair:
        return UniswapPair(web3=self.web3, pair_address=self.factory.get_pair_address(first_token, second_token))

    def get_factory_address(self) -> Address:
        return Address(self._contract.functions.factory().call())

    def get_quote(self, first_token: Address, second_token: Address, first_token_amount: Wad) -> Wad:
        pair = self.get_pair(first_token=first_token, second_token=second_token)
        reserves = pair.reserves

        return Wad(self._contract.functions.quote(first_token_amount.value, reserves.first_token_amount.value, reserves.second_token_amount.value).call())

    def get_amount_input(self, first_token: Address, second_token: Address, amount_output: Wad) -> Wad:
        pair = self.get_pair(first_token=first_token, second_token=second_token)
        reserves = pair.reserves

        return Wad(self._contract.functions.getAmountIn(amount_output.value, reserves.first_token_amount.value,
                                                        reserves.second_token_amount.value).call())

    def get_amount_output(self, first_token: Address, second_token: Address, amount_input: Wad) -> Wad:
        pair = self.get_pair(first_token=first_token, second_token=second_token)
        reserves = pair.reserves

        return Wad(self._contract.functions.getAmountOut(amount_input.value, reserves.first_token_amount.value,
                                                         reserves.second_token_amount.value).call())

    def get_amounts_out(self, amount_in: Wad, path: List[Address]) -> List[Wad]:
        result = self._contract.functions.getAmountsOut(amount_in.value, [address.address for address in path]).call()
        return [Wad(amount) for amount in result]

    def get_amounts_in(self, amount_out: Wad, path: List[Address]) -> List[Wad]:
        result = self._contract.functions.getAmountsIn(amount_out.value, [address.address for address in path]).call()
        return [Wad(amount) for amount in result]

    def add_liquidity(self, first_token: Address, second_token: Address, first_token_amount: Wad, second_token_amount: Wad) -> Transact:
        assert(isinstance(first_token_amount, Wad))
        assert(isinstance(second_token_amount, Wad))
        assert(isinstance(first_token, Address))
        assert(isinstance(second_token, Address))

        first_token_min_amount = Wad.from_number(0.5) * first_token_amount
        second_token_min_amount = Wad.from_number(0.5) * second_token_amount

        if first_token == self.zero_address:
            return Transact(self, self.web3, self.abi, self.address, self._contract, 'addLiquidityETH',
                            [second_token.address, second_token_amount.value, second_token_min_amount.value, first_token_min_amount.value,
                             self.account_address.address, self._deadline()], {'value': first_token_amount.value})
        elif second_token == self.zero_address:

            return Transact(self, self.web3, self.abi, self.address, self._contract, 'addLiquidityETH',
                            [first_token.address, first_token_amount.value, first_token_min_amount.value, second_token_min_amount.value,
                             self.account_address.address, self._deadline()], {'value': second_token_amount.value})
        else:

            return Transact(self, self.web3, self.abi, self.address, self._contract, 'addLiquidity',
                            [first_token.address, second_token.address, first_token_amount.value, second_token_amount.value, first_token_min_amount.value,
                             second_token_min_amount.value, self.account_address.address, self._deadline()])

    def remove_liquidity(self, first_token: Address, second_token: Address, amount: Wad) -> Transact:
        assert(isinstance(amount, Wad))
        assert (isinstance(first_token, Address))
        assert (isinstance(second_token, Address))

        first_token_min_amount = Wad.from_number(0.5) * amount
        second_token_min_amount = Wad.from_number(0.5) * amount

        if first_token == self.zero_address:
            return Transact(self, self.web3, self.abi, self.address, self._contract, 'removeLiquidityETH',
                            [second_token, amount, second_token_min_amount.value, first_token_min_amount.value,
                             self.account_address, self._deadline()])
        elif second_token == self.zero_address:
            return Transact(self, self.web3, self.abi, self.address, self._contract, 'removeLiquidityETH',
                            [first_token, amount, first_token_min_amount.value, second_token_min_amount.value,
                             self.account_address, self._deadline()])
        else:
            return Transact(self, self.web3, self.abi, self.address, self._contract, 'removeLiquidity',
                            [first_token, second_token, amount, first_token_min_amount.value,
                             second_token_min_amount.value, self.account_address, self._deadline()])

    def __swap_exact_tokens_for_tokens(self, amount_in: Wad, min_amount_out: Wad, path: List[Address]) -> Transact:
        assert (isinstance(amount_in, Wad))
        assert (isinstance(min_amount_out, Wad))
        assert (isinstance(path, list))

        return Transact(self, self.web3, self.abi, self.address, self._contract, 'swapExactTokensForTokens',
                        [amount_in.value, min_amount_out.value, [address.address for address in path],
                         self.account_address.address, self._deadline()])

    def __swap_exact_eth_for_tokens(self, amount_in: Wad, min_amount_out: Wad, path: List[Address]) -> Transact:
        assert (isinstance(amount_in, Wad))
        assert (isinstance(min_amount_out, Wad))
        assert (isinstance(path, list))

        return Transact(self, self.web3, self.abi, self.address, self._contract, 'swapExactETHForTokens',
                        [min_amount_out.value, [address.address for address in path],
                         self.account_address.address, self._deadline()],
                        {'value': amount_in.value})

    def __swap_exact_tokens_for_eth(self, amount_in: Wad, min_amount_out: Wad, path: List[Address]) -> Transact:
        assert (isinstance(amount_in, Wad))
        assert (isinstance(min_amount_out, Wad))
        assert (isinstance(path, list))

        return Transact(self, self.web3, self.abi, self.address, self._contract, 'swapExactTokensForETH',
                        [amount_in.value, min_amount_out.value, [address.address for address in path],
                         self.account_address.address, self._deadline()])

    def __swap_tokens_for_exact_tokens(self, amount_out: Wad, max_amount_in: Wad, path: List[Address]) -> Transact:
        assert (isinstance(amount_out, Wad))
        assert (isinstance(max_amount_in, Wad))
        assert (isinstance(path, list))

        return Transact(self, self.web3, self.abi, self.address, self._contract, 'swapTokensForExactTokens',
                        [amount_out.value, max_amount_in.value, [address.address for address in path],
                         self.account_address.address, self._deadline()]
                        )

    def __swap_tokens_for_exact_eth(self, amount_out: Wad, max_amount_in: Wad, path: List[Address]) -> Transact:
        assert (isinstance(amount_out, Wad))
        assert (isinstance(max_amount_in, Wad))
        assert (isinstance(path, list))

        return Transact(self, self.web3, self.abi, self.address, self._contract, 'swapTokensForExactETH',
                        [amount_out.value, max_amount_in.value, [address.address for address in path],
                         self.account_address.address, self._deadline()]
                        )

    def __swap_eth_for_exact_tokens(self, amount_out: Wad, max_amount_in: Wad, path: List[Address]) -> Transact:
        assert (isinstance(amount_out, Wad))
        assert (isinstance(max_amount_in, Wad))
        assert (isinstance(path, list))

        return Transact(self, self.web3, self.abi, self.address, self._contract, 'swapETHForExactTokens',
                        [amount_out.value, [address.address for address in path],
                         self.account_address.address, self._deadline()],
                        {'value': max_amount_in.value}
                        )

    def swap_from_exact_amount(self, amount_in: Wad, min_amount_out: Wad, path: List[Address]) -> Transact:
        assert len(path) >= 2, 'len(path) <2 (the number of tokens in the swap must be more than 2)'

        if path[0] == self.zero_address:
            return self.__swap_exact_eth_for_tokens(amount_in=amount_in, min_amount_out=min_amount_out, path=path)
        elif path[-1] == self.zero_address:
            return self.__swap_exact_tokens_for_eth(amount_in=amount_in, min_amount_out=min_amount_out, path=path)
        else:
            return self.__swap_exact_tokens_for_tokens(amount_in=amount_in, min_amount_out=min_amount_out, path=path)

    def swap_to_exact_amount(self, max_amount_in, amount_out, path: List[Address]) -> Transact:
        assert len(path) >= 2, 'len(path) <2 (the number of tokens in the swap must be more than 2)'

        if path[0] == self.zero_address:
            return self.__swap_eth_for_exact_tokens(amount_out=amount_out, max_amount_in=max_amount_in, path=path)
        elif path[-1] == self.zero_address:
            return self.__swap_tokens_for_exact_eth(amount_out=amount_out, max_amount_in=max_amount_in, path=path)
        else:
            return self.__swap_tokens_for_exact_tokens(amount_out=amount_out, max_amount_in=max_amount_in, path=path)

    def _deadline(self):
        """Get a predefined deadline."""
        return int(time.time()) + 1000

    def __eq__(self, other):
        assert(isinstance(other, UniswapRouter))
        return self.address == other.address

    def __repr__(self):
        return f"UniswapRouter('{self.address}')"


class MarketMaker:
    router: UniswapRouter = None

    def __init__(self, router: UniswapRouter):
        assert (isinstance(router, UniswapRouter))

        self.router = router

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
    def _get_amounts(market_price: Wad, first_token_liquidity_pool_amount: Wad, second_token_liquidity_pool_amount: Wad):
        liquidity_pool_constant = first_token_liquidity_pool_amount * second_token_liquidity_pool_amount

        new_first_token_liquidity_pool_amount = sqrt(liquidity_pool_constant * market_price)
        new_second_token_liquidity_pool_amount = sqrt(liquidity_pool_constant / market_price)

        return AttrDict({
            'exact_value': first_token_liquidity_pool_amount - Wad.from_number(new_first_token_liquidity_pool_amount),
            'limit': Wad.from_number(new_second_token_liquidity_pool_amount) - second_token_liquidity_pool_amount,
        })

    def set_price(self, market_price: Wad, first_token: Address, second_token: Address, max_delta_on_percent: int) -> Transact:
        pair = self.router.get_pair(first_token=first_token, second_token=second_token)

        reserves = pair.reserves.map()

        uniswap_price = reserves[first_token] / reserves[second_token]
        delta = (market_price.value * 100 / uniswap_price.value) - 100

        if delta > max_delta_on_percent:
            input_data = self._get_amounts(market_price=market_price,
                                           first_token_liquidity_pool_amount=reserves[first_token],
                                           second_token_liquidity_pool_amount=reserves[second_token])

            a = self.router.get_amounts_out(amount_in=abs(input_data.exact_value), path=[first_token, second_token])

            return self.router.swap_from_exact_amount(amount_in=abs(input_data.exact_value),
                                                      min_amount_out=a[-1],
                                                      path=[first_token, second_token])

        elif delta < 0 and abs(delta) > max_delta_on_percent:
            input_data = self._get_amounts(market_price=market_price,
                                           first_token_liquidity_pool_amount=reserves[first_token],
                                           second_token_liquidity_pool_amount=reserves[second_token])

            a = self.router.get_amounts_in(amount_out=abs(input_data.exact_value), path=[second_token, first_token])

            return self.router.swap_to_exact_amount(amount_out=abs(input_data.exact_value),
                                                    max_amount_in=a[0],
                                                    path=[second_token, first_token])
        else:
            print()
