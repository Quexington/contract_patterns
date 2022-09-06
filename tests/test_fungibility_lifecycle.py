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
from clvm_contracts.strict_fungibility import CATType, NFTType, SingletonType
from clvm_contracts.validating_meta_puzzle import (
    AssetType,
    INNER_PUZZLE_PREFIX,
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
async def test_cat_lifecycle():
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
        cat_type = CATType.new(
            basic_type.launcher_hash, basic_type.remover_hash, basic_type.environment
        )
        cat_vmp = VMP(ACS, [cat_type])

        # Create a solution adding it to the vmp
        add_cat_type_spend = VMPSpend(
            vmp_coin,
            empty_vmp,
            type_additions=[BasicType.launch(cat_type, conditions=Program.to(None))],
        )
        solved_add_cat_type_spend = CATType.solve([add_cat_type_spend])[0]
        solved_add_cat_type_spend.inner_solution = Program.to(
            [
                [51, ACS_PH, vmp_coin.amount],
                [1, solved_add_cat_type_spend.security_hash()],
            ]
        )
        add_cat_type_bundle = SpendBundle(
            [solved_add_cat_type_spend.to_coin_spend()],
            G2Element(),
        )
        result = await sim_client.push_tx(add_cat_type_bundle)
        await sim.farm_block()
        assert result == (MempoolInclusionStatus.SUCCESS, None)
        logger.add_cost("CAT addition", add_cat_type_bundle)
        logger.log_cost_statistics()

    finally:
        await sim.close()


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
            [solved_add_nft_type_spend.to_coin_spend()],
            G2Element(),
        )
        result = await sim_client.push_tx(add_nft_type_bundle)
        await sim.farm_block()
        assert result == (MempoolInclusionStatus.SUCCESS, None)
        logger.add_cost("NFT addition", add_nft_type_bundle)
        logger.log_cost_statistics()

    finally:
        await sim.close()


@pytest.mark.asyncio
async def test_singleton_lifecycle():
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
        singleton_type = SingletonType.new(
            vmp_coin.name(), basic_type.remover_hash, basic_type.environment
        )
        singleton_vmp = VMP(ACS, [singleton_type])

        # Create a solution adding it to the vmp
        add_singleton_type_spend = VMPSpend(
            vmp_coin,
            empty_vmp,
            type_additions=[
                SingletonType.launch(
                    singleton_type, conditions=Program.to(None), coin_id=vmp_coin.name()
                )
            ],
        )
        solved_add_singleton_type_spend = SingletonType.solve(
            [add_singleton_type_spend]
        )[0]
        solved_add_singleton_type_spend.inner_solution = Program.to(
            [
                [51, ACS_PH, vmp_coin.amount],
                [1, solved_add_singleton_type_spend.security_hash()],
            ]
        )
        add_singleton_type_bundle = SpendBundle(
            [solved_add_singleton_type_spend.to_coin_spend()],
            G2Element(),
        )
        result = await sim_client.push_tx(add_singleton_type_bundle)
        await sim.farm_block()
        assert result == (MempoolInclusionStatus.SUCCESS, None)
        logger.add_cost("Singleton addition", add_singleton_type_bundle)

        lineage_proof = LineageProof(
            vmp_coin.parent_coin_info,
            empty_vmp.get_types_hash(),
            empty_vmp.inner_puzzle.get_tree_hash(),
            vmp_coin.amount,
        )
        vmp_coin = (
            await sim_client.get_coin_records_by_puzzle_hash(
                singleton_vmp.get_tree_hash(), include_spent_coins=False
            )
        )[0].coin

        # Farm a p2_singleton
        p2_singleton = SingletonType.p2(launcher_hash=singleton_type.launcher_hash)
        await sim.farm_block(p2_singleton.get_tree_hash())
        p2_singleton_coin: Coin = (
            await sim_client.get_coin_records_by_puzzle_hash(
                p2_singleton.get_tree_hash(), include_spent_coins=False
            )
        )[0].coin

        # Spend a p2_singleton
        p2_singleton_claim_spend = VMPSpend(
            vmp_coin,
            singleton_vmp,
            lineage_proof=lineage_proof,
        )
        solved_p2_singleton_claim_spend = SingletonType.solve(
            [p2_singleton_claim_spend]
        )[0]
        solved_p2_singleton_claim_spend.inner_solution = Program.to(
            [
                [51, ACS_PH, vmp_coin.amount],
                [1, solved_p2_singleton_claim_spend.security_hash()],
                [
                    60,
                    NAMESPACE_PREFIX
                    + INNER_PUZZLE_PREFIX
                    + Program.to((p2_singleton_coin.name(), ACS_PH)).get_tree_hash(),
                ],
            ]
        )
        UNIQUE_AMOUNT = 12345
        p2_singleton_spend = CoinSpend(
            p2_singleton_coin,
            p2_singleton,
            SingletonType.solve_p2(
                vmp_spend=solved_p2_singleton_claim_spend,
                coin=p2_singleton_coin,
                puzzle=ACS,
                solution=Program.to([[51, ACS_PH, UNIQUE_AMOUNT]]),
            ),
        )
        p2_singleton_claim_bundle = SpendBundle(
            [
                solved_p2_singleton_claim_spend.to_coin_spend(),
                p2_singleton_spend,
            ],
            G2Element(),
        )
        result = await sim_client.push_tx(p2_singleton_claim_bundle)
        await sim.farm_block()
        assert result == (MempoolInclusionStatus.SUCCESS, None)
        logger.add_cost("P2 Singleton claim", add_singleton_type_bundle)

        acs_coins = (
            await sim_client.get_coin_records_by_puzzle_hash(
                ACS_PH, include_spent_coins=False
            )
        )
        assert len(list(c for c in acs_coins if c.coin.amount == UNIQUE_AMOUNT)) == 1

        logger.log_cost_statistics()

    finally:
        await sim.close()
