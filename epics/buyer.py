from random import randint

from epics.price import PriceService


class Buyer:

    def __init__(self, price_service: PriceService) -> None:
        self.price_service = price_service

    def buy_packs(self, pack_id: int, amount: int) -> bool:
        left = amount
        batch_size = amount // 4
        while left:
            n = randint(1, min(batch_size if batch_size else amount, left))
            res = self.price_service.buy_pack(pack_id, n)
            if res:
                print(f'Bought {n} pack(s) {pack_id}')
                left -= n

        return True
