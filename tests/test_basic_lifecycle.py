import pytest

from blspy import G2Element

from chia.clvm.spend_sim import SpendSim, SimClient
from chia.types.blockchain_format.coin import Coin
from chia.types.blockchain_format.program import Program
from chia.types.blockchain_format.sized_bytes import bytes32
from chia.types.coin_spend import CoinSpend
from chia.types.mempool_inclusion_status import MempoolInclusionStatus
from chia.types.spend_bundle import SpendBundle
from chia.wallet.puzzles.load_clvm import load_clvm

from clvm_contracts.validating_meta_puzzle import (
    AssetType,
    LineageProof,
    NAMESPACE_PREFIX,
    SecuredInformation,
    VMP,
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
        LAUNCHER = load_clvm(
            "launcher.clsp", package_or_requirement="clvm_contracts.boilerplate"
        )
        ENVIRONMENT = Program.to(None)
        PRE_VALIDATOR = load_clvm(
            "pre_validator.clsp", package_or_requirement="clvm_contracts.boilerplate"
        )
        VALIDATOR = load_clvm(
            "validator.clsp", package_or_requirement="clvm_contracts.boilerplate"
        )
        REMOVER = load_clvm(
            "remover.clsp", package_or_requirement="clvm_contracts.boilerplate"
        )

        basic_type = AssetType(
            LAUNCHER.get_tree_hash(),
            ENVIRONMENT,
            PRE_VALIDATOR,
            VALIDATOR,
            REMOVER,
        )

        # Create a solution adding it to the vmp
        launcher_solution = Program.to(([ENVIRONMENT, PRE_VALIDATOR, VALIDATOR, REMOVER], None))
        secured_info = SecuredInformation(
            [(LAUNCHER, launcher_solution)],
            [None],
            [None],
        )
        add_basic_type_bundle = SpendBundle(
            [
                CoinSpend(
                    vmp_coin,
                    empty_vmp.construct(),
                    empty_vmp.solve(
                        Program.to(
                            [
                                [51, ACS_PH, vmp_coin.amount],
                                [1, secured_info.get_tree_hash()],
                            ]
                        ),
                        None,
                        [None],
                        secured_info,
                    ),
                )
            ],
            G2Element(),
        )
        result = await sim_client.push_tx(add_basic_type_bundle)
        await sim.farm_block()
        assert result == (MempoolInclusionStatus.SUCCESS, None)

        # Reconstruct the VMP and make sure we found it correctly
        basic_vmp = VMP(ACS, [basic_type])
        lineage_proof = LineageProof(
            vmp_coin.parent_coin_info,
            basic_vmp.get_types_hash(),
            ACS_PH,
            vmp_coin.amount,
        )
        vmp_coin: Coin = (
            await sim_client.get_coin_records_by_puzzle_hash(
                basic_vmp.get_tree_hash(), include_spent_coins=False
            )
        )[0].coin

        # Now let's test a bunch of failure cases
        secured_info = SecuredInformation(
            [],
            [None],
            [None],
        )
        # Create banned announcements from the inner_puzzle
        for opcode in (60,62):
            illegal_innerpuz_announcement_bundle = SpendBundle(
                [
                    CoinSpend(
                        vmp_coin,
                        basic_vmp.construct(),
                        basic_vmp.solve(
                            Program.to(
                                [
                                    [51, ACS_PH, vmp_coin.amount],
                                    [1, secured_info.get_tree_hash()],
                                    [opcode, NAMESPACE_PREFIX + bytes32([1] * 32)],
                                ]
                            ),
                            lineage_proof,
                            [None],
                            secured_info,
                        ),
                    )
                ],
                G2Element(),
            )
            with pytest.raises(ValueError, match="clvm raise"):
                illegal_innerpuz_announcement_bundle.coin_spends[
                    0
                ].puzzle_reveal.to_program().run(
                    illegal_innerpuz_announcement_bundle.coin_spends[0].solution.to_program()
                )

        # Now let's test banned announcements from the pre-validator
        bad_secured_info = SecuredInformation(
            [],
            [None],
            [[[opcode, NAMESPACE_PREFIX + bytes32([1] * 32)]]],
        )
        for opcode in (60,62):
            illegal_launcher_announcement_bundle = SpendBundle(
                [
                    CoinSpend(
                        vmp_coin,
                        basic_vmp.construct(),
                        basic_vmp.solve(
                            Program.to(
                                [
                                    [51, ACS_PH, vmp_coin.amount],
                                    [1, bad_secured_info.get_tree_hash()],
                                ]
                            ),
                            lineage_proof,
                            [None],
                            bad_secured_info,
                        ),
                    )
                ],
                G2Element(),
            )
            with pytest.raises(ValueError, match="clvm raise"):
                illegal_launcher_announcement_bundle.coin_spends[
                    0
                ].puzzle_reveal.to_program().run(
                    illegal_launcher_announcement_bundle.coin_spends[0].solution.to_program()
                )
    finally:
        await sim.close()
