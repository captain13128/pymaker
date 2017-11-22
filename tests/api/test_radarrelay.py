# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017 reverendus
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

import json

import pkg_resources
from web3 import EthereumTesterProvider
from web3 import Web3

from keeper.api import Address
from keeper.api.radarrelay import RadarRelay


class TestRadarRelay:
    #TODO duplicate of the deploy method in conftest.py
    def deploy(self, web3, contract_name, args=None):
        contract_factory = web3.eth.contract(abi=json.loads(pkg_resources.resource_string('keeper.api.feed', f'abi/{contract_name}.abi')),
                                             bytecode=pkg_resources.resource_string('keeper.api.feed', f'abi/{contract_name}.bin'))
        tx_hash = contract_factory.deploy(args=args)
        receipt = web3.eth.getTransactionReceipt(tx_hash)
        return receipt['contractAddress']

    def setup_method(self):
        self.web3 = Web3(EthereumTesterProvider())
        self.web3.eth.defaultAccount = self.web3.eth.accounts[0]
        self.our_address = Address(self.web3.eth.defaultAccount)
        self.zrx_token_address = self.deploy(self.web3, 'ZRXToken')
        self.token_transfer_proxy_address = self.deploy(self.web3, 'TokenTransferProxy')
        self.radarrelay = RadarRelay.deploy(self.web3,
                                            Address(self.zrx_token_address),
                                            Address(self.token_transfer_proxy_address))

    def test_correct_deployment(self):
        # expect
        assert self.radarrelay is not None
        assert self.radarrelay.address is not None
        assert self.radarrelay.zrx_token() == Address(self.zrx_token_address)
        assert self.radarrelay.token_transfer_proxy() == Address(self.token_transfer_proxy_address)

    def test_should_have_printable_representation(self):
        assert repr(self.radarrelay) == f"RadarRelay()"