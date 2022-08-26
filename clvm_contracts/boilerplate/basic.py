from chia.types.blockchain_format.program import Program
from chia.wallet.puzzles.load_clvm import load_clvm

from clvm_contracts.validating_meta_puzzle import AssetType

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

class BasicType:
    @staticmethod
    def new():
        return AssetType(
            LAUNCHER.get_tree_hash(),
            ENVIRONMENT,
            PRE_VALIDATOR,
            VALIDATOR,
            REMOVER.get_tree_hash(),
        )