from collections import defaultdict
from schema import Transaction, Cycle, BuyRecord, SellRecord


def build_cycles(transactions: list) -> list:
    """
    Groups transactions into closed buy→sell cycles per ticker.
    Handles partial buys/sells and averaging-down detection.
    Open (unclosed) positions are silently excluded.
    """
    by_ticker: dict = defaultdict(list)
    for t in transactions:
        by_ticker[t.ticker].append(t)

    cycles = []
    for ticker, txns in by_ticker.items():
        txns = sorted(txns, key=lambda x: x.executed_at)
        pos_qty = 0
        avg_cost = 0.0
        cur: Cycle | None = None

        for order in txns:
            if order.side == "BUY":
                if pos_qty == 0:
                    cur = Cycle(ticker=ticker, entry_ts=order.executed_at)

                in_loss = (pos_qty > 0) and (order.price < avg_cost)
                avg_cost = (avg_cost * pos_qty + order.price * order.qty) / (pos_qty + order.qty)
                pos_qty += order.qty
                cur.buys.append(BuyRecord(ts=order.executed_at, price=order.price,
                                          qty=order.qty, in_loss=in_loss))
                cur.cost_checkpoints.append((order.executed_at, avg_cost))

            else:  # SELL
                if cur is None:
                    continue
                sell_qty = min(order.qty, pos_qty)
                cur.sells.append(SellRecord(ts=order.executed_at, price=order.price, qty=sell_qty))
                pos_qty -= sell_qty

                if pos_qty == 0:
                    cur.exit_ts = order.executed_at
                    total_buy_cost = sum(b.price * b.qty for b in cur.buys)
                    total_sell_proc = sum(s.price * s.qty for s in cur.sells)
                    total_buy_qty = sum(b.qty for b in cur.buys)
                    cur.avg_buy_price = total_buy_cost / total_buy_qty if total_buy_qty else 0.0
                    cur.realized_return = (
                        (total_sell_proc - total_buy_cost) / total_buy_cost * 100
                        if total_buy_cost else 0.0
                    )
                    cur.avg_down_count = sum(1 for b in cur.buys if b.in_loss)
                    first_buy_qty = cur.buys[0].qty if cur.buys else 1
                    avg_down_qty_total = sum(b.qty for b in cur.buys if b.in_loss)
                    cur.avg_down_qty = avg_down_qty_total / first_buy_qty
                    cycles.append(cur)
                    cur = None

        # pos_qty > 0 at end → unclosed position, excluded per spec

    return cycles
