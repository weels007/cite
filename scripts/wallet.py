"""Load wallets from the weels wallet folder. Nothing is written anywhere.

The folder ``D:\\Genlayer-project\\weels\\wallet`` is the single source of
truth for every wallet in this workspace. The GenLayer CLI store is never
used, so no copy of a private key ever lands outside that folder.

The folder can be moved. Set ``CITE_WALLET_FOLDER`` to point somewhere else,
or keep a ``wallet`` folder next to the project.
"""

import json
import os
from pathlib import Path

from eth_account import Account

FALLBACK_WALLET_FOLDER = Path(r"D:\Genlayer-project\weels\wallet")


def wallet_folder() -> Path:
    """Where the keystores live."""
    configured = os.environ.get("CITE_WALLET_FOLDER")
    if configured:
        return Path(configured)
    if FALLBACK_WALLET_FOLDER.exists():
        return FALLBACK_WALLET_FOLDER
    return Path(__file__).resolve().parents[1] / "wallet"


WALLET_FOLDER = wallet_folder()

# The wallet this project uses by default.
DEFAULT_WALLET = "cite"


def load_account(name: str = DEFAULT_WALLET):
    """Decrypt a keystore from the wallet folder and return the account."""
    keystore = WALLET_FOLDER / f"{name}-keystore.json"
    password_file = WALLET_FOLDER / f"{name}.password"
    if not keystore.exists():
        available = sorted(
            path.name.replace("-keystore.json", "")
            for path in WALLET_FOLDER.glob("*-keystore.json")
        )
        raise SystemExit(
            f"no wallet '{name}' in {WALLET_FOLDER}\n"
            f"available there: {', '.join(available) or '(none)'}\n"
            "Create it there, never somewhere else."
        )
    password = (
        password_file.read_text(encoding="utf-8").strip()
        if password_file.exists()
        else ""
    )
    data = json.loads(keystore.read_text(encoding="utf-8"))
    return Account.from_key(Account.decrypt(data, password))


def add_wallet_argument(parser, default: str = DEFAULT_WALLET) -> None:
    parser.add_argument(
        "--wallet",
        default=default,
        help="wallet name inside the weels wallet folder (default: %(default)s)",
    )
