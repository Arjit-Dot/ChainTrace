"""Shared test helpers: an in-memory chain adapter and a transfer builder."""
from engine.chains.tron import Transfer

T0 = 1_700_000_000


class FakeAdapter:
    """Serves transfers from memory, like TronAdapter.transfers()."""
    offline = True

    def __init__(self, transfers):
        self.all = transfers

    def transfers(self, addr):
        mine = [t for t in self.all if addr in (t.from_addr, t.to_addr)]
        if not mine:
            raise LookupError(addr)
        return sorted(mine, key=lambda t: t.timestamp), "cached"


def tx(src, dst, amount, ts=T0, h=None):
    return Transfer(tx_hash=h or f"{src}{dst}{ts}{amount}", from_addr=src, to_addr=dst, amount=amount, timestamp=ts)
