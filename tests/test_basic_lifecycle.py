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
from clvm_contracts.validating_meta_puzzle import (
    AssetType,
    LineageProof,
    NAMESPACE_PREFIX,
    TypeProof,
    TypeChange,
    VMP,
    VMPSpend,
)

ACS = Program.to(1)
ACS_PH = ACS.get_tree_hash()


@pytest.mark.asyncio
async def test_basic_lifecycle():
    sim = await SpendSim.create()
    try:
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
        basic_vmp = VMP(ACS, [basic_type])

        # Create a solution adding it to the vmp
        basic_spend = VMPSpend(
            vmp_coin,
            empty_vmp,
            type_additions=[BasicType.launch(basic_type, conditions=Program.to(None))],
        )
        basic_spend.inner_solution = Program.to(
            [
                [51, ACS_PH, vmp_coin.amount],
                [1, basic_spend.security_hash()],
            ]
        )
        add_basic_type_bundle = SpendBundle([basic_spend.to_coin_spend()], G2Element())
        result = await sim_client.push_tx(add_basic_type_bundle)
        await sim.farm_block()
        assert result == (MempoolInclusionStatus.SUCCESS, None)

        lineage_proof = LineageProof(
            vmp_coin.parent_coin_info,
            empty_vmp.get_types_hash(),
            empty_vmp.inner_puzzle.get_tree_hash(),
            vmp_coin.amount,
        )
        vmp_coin: Coin = (
            await sim_client.get_coin_records_by_puzzle_hash(
                basic_vmp.get_tree_hash(), include_spent_coins=False
            )
        )[0].coin

        # Now let's test some failure cases
        # Create banned announcements from the inner_puzzle
        for opcode in (60, 62):
            illegal_innerpuz_announcement_spend = VMPSpend(
                vmp_coin,
                basic_vmp,
                lineage_proof=lineage_proof,
            )
            illegal_innerpuz_announcement_spend.inner_solution = Program.to(
                [
                    [51, ACS_PH, vmp_coin.amount],
                    [
                        1,
                        illegal_innerpuz_announcement_spend.security_hash(),
                    ],
                    [opcode, NAMESPACE_PREFIX + bytes32([1] * 32)],
                ]
            )
            illegal_innerpuz_announcement_bundle = SpendBundle(
                [illegal_innerpuz_announcement_spend.to_coin_spend()],
                G2Element(),
            )
            with pytest.raises(ValueError, match="clvm raise"):
                illegal_innerpuz_announcement_bundle.coin_spends[
                    0
                ].puzzle_reveal.to_program().run(
                    illegal_innerpuz_announcement_bundle.coin_spends[
                        0
                    ].solution.to_program()
                )

        # Now let's test banned announcements from the pre-validator
        for opcode in (60, 62):
            illegal_pre_val_announcement_spend = VMPSpend(
                vmp_coin,
                basic_vmp,
                lineage_proof=lineage_proof,
                secure_solutions=[
                    Program.to([[opcode, NAMESPACE_PREFIX + bytes32([1] * 32)]])
                ],
            )
            illegal_pre_val_announcement_spend.inner_solution = Program.to(
                [
                    [51, ACS_PH, vmp_coin.amount],
                    [1, illegal_pre_val_announcement_spend.security_hash()],
                ]
            )
            illegal_pre_val_announcement_bundle = SpendBundle(
                [illegal_pre_val_announcement_spend.to_coin_spend()],
                G2Element(),
            )
            with pytest.raises(ValueError, match="clvm raise"):
                illegal_pre_val_announcement_bundle.coin_spends[
                    0
                ].puzzle_reveal.to_program().run(
                    illegal_pre_val_announcement_bundle.coin_spends[
                        0
                    ].solution.to_program()
                )

        # Try to create a bad announcement while removing the type
        for opcode in (60, 62):
            illegal_remover_announcement_spend = VMPSpend(
                vmp_coin,
                basic_vmp,
                lineage_proof=lineage_proof,
                type_removals=[
                    BasicType.remove(
                        basic_type,
                        conditions=Program.to(
                            [[opcode, NAMESPACE_PREFIX + bytes32([1] * 32)]]
                        ),
                    )
                ],
            )
            illegal_remover_announcement_spend.inner_solution = Program.to(
                [
                    [51, ACS_PH, vmp_coin.amount],
                    [1, illegal_remover_announcement_spend.security_hash()],
                ]
            )
            illegal_remover_announcement_bundle = SpendBundle(
                [illegal_remover_announcement_spend.to_coin_spend()],
                G2Element(),
            )
            with pytest.raises(ValueError, match="clvm raise"):
                illegal_remover_announcement_bundle.coin_spends[
                    0
                ].puzzle_reveal.to_program().run(
                    illegal_remover_announcement_bundle.coin_spends[
                        0
                    ].solution.to_program()
                )

        # Now let's try to honestly remove the type
        remover_spend = VMPSpend(
            vmp_coin,
            basic_vmp,
            lineage_proof=lineage_proof,
            type_removals=[
                BasicType.remove(
                    basic_type,
                    conditions=Program.to(None),
                )
            ],
        )
        remover_spend.inner_solution = Program.to(
            [
                [51, ACS_PH, vmp_coin.amount],
                [1, remover_spend.security_hash()],
            ]
        )
        remover_bundle = SpendBundle(
            [remover_spend.to_coin_spend()],
            G2Element(),
        )
        result = await sim_client.push_tx(remover_bundle)
        await sim.farm_block()
        assert result == (MempoolInclusionStatus.SUCCESS, None)

        # Assert that the VMP was cleared from the new coin
        acs_coin = (
            await sim_client.get_coin_records_by_parent_ids(
                [vmp_coin.name()], include_spent_coins=False
            )
        )[0].coin
        assert acs_coin.puzzle_hash == ACS_PH

    finally:
        await sim.close()
