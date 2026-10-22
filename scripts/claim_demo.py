"""Claim a payout and confirm the delivery, to show the recovery path works."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from genlayer_py import create_client, studionet
from wallet import load_account

CONTRACT = "0xB0295bcBe44271D194Da693BFd6844022F413958"
MARKET_ID = 0


def main() -> int:
    creator = load_account("tester1")
    bettor = load_account("tester2")
    client = create_client(studionet, account=creator)

    def accounting(label: str) -> None:
        data = client.read_contract(CONTRACT, "get_accounting")
        print(
            f"  {label:<22} staked={data['total_staked_all']} "
            f"paid={data['paid_out_all']} owed={data['owed_all']} "
            f"in_flight={data['in_flight_all']} balance={data['contract_balance']} "
            f"invariant={data['invariant_holds']}"
        )

    print("== before ==")
    accounting("start")

    print("== claim ==")
    tx = client.write_contract(
        address=CONTRACT,
        function_name="claim",
        account=bettor,
        args=[MARKET_ID],
    )
    client.wait_for_transaction_receipt(tx)
    time.sleep(2)
    accounting("after claim")

    pending = client.read_contract(CONTRACT, "get_pending_payouts")
    print(f"  pending payouts       {pending['count']}")
    for entry in pending["pending"]:
        print(f"    market {entry['market_id']} owed {entry['owed']} delivered {entry['delivered']}")

    print("== claim again (the retry, it must not pay twice) ==")
    tx = client.write_contract(
        address=CONTRACT,
        function_name="claim",
        account=bettor,
        args=[MARKET_ID],
    )
    client.wait_for_transaction_receipt(tx)
    time.sleep(2)
    accounting("after retry")

    print("== confirm the delivery ==")
    tx = client.write_contract(
        address=CONTRACT,
        function_name="confirm_payout",
        account=bettor,
        args=[MARKET_ID, 0],
    )
    client.wait_for_transaction_receipt(tx)
    time.sleep(2)
    accounting("after confirm")

    pending = client.read_contract(CONTRACT, "get_pending_payouts")
    print(f"  pending payouts       {pending['count']}")

    print("== confirm again (must be refused) ==")
    tx = client.write_contract(
        address=CONTRACT,
        function_name="confirm_payout",
        account=bettor,
        args=[MARKET_ID, 0],
    )
    receipt = client.wait_for_transaction_receipt(tx)
    result = str(receipt.get("execution_result") or receipt.get("status") or "")
    print(f"  receipt: {result}")
    if result in ("ERROR", "REJECTED", "UNDETERMINED"):
        print("  refused as expected")
    else:
        print("  UNEXPECTED: the second confirmation went through")
    accounting("after the refusal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
