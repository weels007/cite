"""Create the Cite wallet inside the weels wallet folder.

    python scripts/create_wallet.py --name cite

The keypair is generated on the spot and written to
``D:\\Genlayer-project\\weels\\wallet\\<name>-keystore.json`` next to a
``<name>.password`` file, exactly like the other wallets in that folder. The
GenLayer CLI store is deliberately not touched: this folder stays the single
source of truth for every wallet in this workspace.
"""

import argparse
import json
import secrets
import string
import sys
from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_keyfile import create_keyfile_json

WALLET_FOLDER = Path(r"D:\Genlayer-project\weels\wallet")

# The same scrypt parameters the other wallets in the folder use, so that
# decrypting them costs the same everywhere.
SCRYPT_PARAMS = {"n": 2**18, "r": 8, "p": 1, "dklen": 32}


def make_password(length: int = 43) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True, help="wallet name, e.g. cite")
    parser.add_argument(
        "--folder", default=str(WALLET_FOLDER), help="where the wallet is written"
    )
    arguments = parser.parse_args()

    folder = Path(arguments.folder)
    folder.mkdir(parents=True, exist_ok=True)

    keystore_path = folder / f"{arguments.name}-keystore.json"
    password_path = folder / f"{arguments.name}.password"
    if keystore_path.exists():
        raise SystemExit(f"{keystore_path} already exists, refusing to overwrite it")

    password = make_password()
    account = Account.create()
    keystore = create_keyfile_json(
        account.key, password, version=3, kdf="scrypt", iterations=SCRYPT_PARAMS["n"]
    )
    # Match the layout the other wallets in the folder use.
    keystore = {
        "address": keystore["address"].replace("0x", ""),
        "crypto": keystore["crypto"],
        "id": keystore["id"],
        "version": keystore["version"],
    }

    keystore_path.write_text(json.dumps(keystore, indent=2), encoding="utf-8")
    password_path.write_text(password, encoding="utf-8")

    # Prove it round trips: decrypt it again and check the address matches.
    reloaded = json.loads(keystore_path.read_text(encoding="utf-8"))
    check = Account.from_key(Account.decrypt(reloaded, password))
    assert check.address == account.address, "keystore round trip failed"

    print(f"keystore : {keystore_path}")
    print(f"password : {password_path}")
    print(f"address  : {account.address}")
    print(f"verified : decrypts back to the same address")
    return 0


if __name__ == "__main__":
    sys.exit(main())
