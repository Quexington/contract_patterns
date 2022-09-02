import pytest

from blspy import G2Element

from chia.clvm.spend_sim import SpendSim, SimClient
from chia.types.blockchain_format.coin import Coin
from chia.types.blockchain_format.program import Program
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.types.coin_spend import CoinSpend
from chia.types.mempool_inclusion_status import MempoolInclusionStatus
from chia.types.spend_bundle import SpendBundle

from clvm_contracts.boilerplate.basic import BasicType
from clvm_contracts.strict_fungibility import NFTType
from clvm_contracts.validating_meta_puzzle import (
    AssetType,
    LineageProof,
    NAMESPACE_PREFIX,
    TypeChange,
    VMP,
    VMPSpend,
)

from tests.cost_logger import CostLogger

ACS = Program.to(1)
ACS_PH = ACS.get_tree_hash()


@pytest.mark.asyncio
async def test_nft_lifecycle():
    sim = await SpendSim.create()
    try:
        logger = CostLogger()
        sim_client = SimClient(sim)
        await sim.farm_block()

        # Construct the most basic form of the VMP
        empty_vmp = VMP(ACS, [])
        await sim.farm_block(empty_vmp.get_tree_hash())
        vmp_coin: Coin = (
            await sim_client.get_coin_records_by_puzzle_hash(
                empty_vmp.get_tree_hash(), include_spent_coins=False
            )
        )[0].coin

        # Construct the most basic AssetType
        basic_type = BasicType.new()
        nft_type = NFTType.new(
            basic_type.launcher_hash, basic_type.remover_hash, basic_type.environment
        )
        nft_vmp = VMP(ACS, [nft_type])

        # Create a solution adding it to the vmp
        add_nft_type_spend = VMPSpend(
            vmp_coin,
            empty_vmp,
            type_additions=[BasicType.launch(nft_type, conditions=Program.to(None))],
        )
        solved_add_nft_type_spend = NFTType.solve([add_nft_type_spend])[0]
        solved_add_nft_type_spend.inner_solution = Program.to(
            [
                [51, ACS_PH, vmp_coin.amount],
                [1, solved_add_nft_type_spend.security_hash()],
            ]
        )
        add_nft_type_bundle = SpendBundle(
            [
                solved_add_nft_type_spend.to_coin_spend()
            ],
            G2Element(),
        )
        result = await sim_client.push_tx(add_nft_type_bundle)
        await sim.farm_block()
        assert result == (MempoolInclusionStatus.SUCCESS, None)
        logger.add_cost("NFT addition", add_nft_type_bundle)
        logger.log_cost_statistics()

    finally:
        await sim.close()
