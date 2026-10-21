"""Deploy Cite, reading the wallet straight from the weels wallet folder.

    python scripts/deploy.py --network studionet --wallet tester1

The wallet is decrypted from
``D:\\Genlayer-project\\weels\\wallet\\<name>-keystore.json`` and used
directly. Nothing is imported into the GenLayer CLI store, so that folder
stays the single source of truth for every wallet in this workspace.
"""

import argparse
import json
import sys
from pathlib import Path

from genlayer_py import create_client, localnet, studionet, testnet_bradbury

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wallet import load_account

ROOT = Path(__file__).resolve().parents[1]
WALLET_FOLDER = Path(r"D:\Genlayer-project\weels\wallet")
CONTRACT_PATH = ROOT / "contracts" / "cite.py"

CHAINS = {
    "studionet": studionet,
    "localnet": localnet,
    "testnet_bradbury": testnet_bradbury,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", default="studionet", choices=sorted(CHAINS))
    parser.add_argument("--wallet", default="cite")
    parser.add_argument("--wait", type=int, default=300, help="receipt retries")
    arguments = parser.parse_args()

    chain = CHAINS[arguments.network]
    account = load_account(arguments.wallet)
    print(f"wallet  : {arguments.wallet}  {account.address}")
    print(f"network : {chain.name} (chain {chain.id})")

    client = create_client(chain, account=account)
    code = CONTRACT_PATH.read_text(encoding="utf-8")

    tx_hash = client.deploy_contract(code=code, account=account)
    print(f"tx      : {tx_hash}")

    try:
        receipt = client.wait_for_transaction_receipt(
            tx_hash, retries=arguments.wait, interval=3000
        )
        print(f"receipt : {receipt}")
    except Exception as error:
        print(f"pending : {str(error)[:200]}")

    print()
    print("find the address with:")
    print(f"    python scripts/show_resolutions.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
