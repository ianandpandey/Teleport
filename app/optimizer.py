"""
Load Optimizer - Core algorithm for finding the best combination of orders.

This is basically a multi-dimensional knapsack problem. We want to maximize
payout while staying within weight and volume limits, plus some extra 
constraints around hazmat, routes, and time windows.

I initially tried brute-force enumeration of all 2^n subsets, but that was
way too slow for n=22 orders. Switched to branch-and-bound with aggressive
pruning - now it runs in milliseconds.
"""

from typing import List, Tuple, Dict
from app.models import Order, Truck


class LoadOptimizer:
    """
    Finds the optimal subset of orders that maximizes revenue.
    
    Uses branch-and-bound with several pruning strategies to handle
    up to 22 orders efficiently (the naive approach would be too slow).
    """

    def __init__(self, truck: Truck, orders: List[Order]):
        self.truck = truck
        self.orders = orders
        self.n = len(orders)

    def _check_time_windows(self, order1: Order, order2: Order) -> bool:
        """
        Two orders can go together if their time windows overlap.
        
        Basically: the later pickup must happen before the earlier delivery.
        If order1 needs pickup Dec 5-9 and order2 needs Dec 4-10, they overlap.
        """
        latest_pickup = max(order1.pickup_date, order2.pickup_date)
        earliest_delivery = min(order1.delivery_date, order2.delivery_date)
        return latest_pickup <= earliest_delivery

    def _check_same_route(self, order1: Order, order2: Order) -> bool:
        """Orders must be going the same direction (same origin -> destination)."""
        # normalize strings for comparison - handles minor formatting differences
        origin_match = order1.origin.strip().lower() == order2.origin.strip().lower()
        dest_match = order1.destination.strip().lower() == order2.destination.strip().lower()
        return origin_match and dest_match

    def _check_hazmat_ok(self, order1: Order, order2: Order) -> bool:
        """
        Hazmat can't mix with non-hazmat. Simple rule but easy to forget.
        """
        return order1.is_hazmat == order2.is_hazmat

    def _build_compatibility_masks(self) -> List[int]:
        """
        Pre-calculate which orders can go together.
        
        Store as bitmasks so we can do O(1) lookups during search.
        compat_masks[i] has bit j set if order i and j are compatible.
        """
        masks = [0] * self.n
        
        for i in range(self.n):
            masks[i] |= (1 << i)  # order is always compatible with itself
            
            for j in range(i + 1, self.n):
                # check all three compatibility rules
                can_combine = (
                    self._check_same_route(self.orders[i], self.orders[j]) and
                    self._check_time_windows(self.orders[i], self.orders[j]) and
                    self._check_hazmat_ok(self.orders[i], self.orders[j])
                )
                if can_combine:
                    masks[i] |= (1 << j)
                    masks[j] |= (1 << i)
                    
        return masks

    def optimize(self) -> Tuple[List[str], int, int, int]:
        """
        Main optimization using branch-and-bound.
        
        Returns tuple of (order_ids, total_payout, total_weight, total_volume)
        """
        if self.n == 0:
            return [], 0, 0, 0

        # pre-calculate stuff we'll need repeatedly
        compat_masks = self._build_compatibility_masks()
        payouts = [o.payout_cents for o in self.orders]
        weights = [o.weight_lbs for o in self.orders]
        volumes = [o.volume_cuft for o in self.orders]

        max_weight = self.truck.max_weight_lbs
        max_volume = self.truck.max_volume_cuft

        # process high-value orders first - helps us find good solutions early
        # which means better pruning later
        order_by_value = sorted(range(self.n), key=lambda i: payouts[i], reverse=True)
        
        # suffix sums for upper-bound pruning
        # suffix_payout[i] = max possible payout from orders i..n
        suffix_payout = [0] * (self.n + 1)
        for i in range(self.n - 1, -1, -1):
            suffix_payout[i] = suffix_payout[i + 1] + payouts[order_by_value[i]]

        # using lists as mutable containers (python closure workaround)
        best_payout = [0]
        best_selection = [[]]

        def search(idx: int, selected_mask: int, curr_payout: int, 
                   curr_weight: int, curr_volume: int, valid_orders: int):
            """Recursive search with pruning."""
            
            # found a better solution?
            if curr_payout > best_payout[0]:
                best_payout[0] = curr_payout
                best_selection[0] = [order_by_value[i] for i in range(idx) 
                                     if selected_mask & (1 << i)]

            # done searching
            if idx >= self.n:
                return

            # PRUNE: even if we took everything remaining, can't beat best
            if curr_payout + suffix_payout[idx] <= best_payout[0]:
                return

            order_idx = order_by_value[idx]

            # option 1: include this order (if compatible and fits)
            if valid_orders & (1 << order_idx):
                new_weight = curr_weight + weights[order_idx]
                new_volume = curr_volume + volumes[order_idx]
                
                if new_weight <= max_weight and new_volume <= max_volume:
                    # narrow down valid orders to only those compatible with this one
                    new_valid = valid_orders & compat_masks[order_idx]
                    search(idx + 1, selected_mask | (1 << idx),
                           curr_payout + payouts[order_idx],
                           new_weight, new_volume, new_valid)

            # option 2: skip this order
            search(idx + 1, selected_mask, curr_payout, 
                   curr_weight, curr_volume, valid_orders)

        # kick off the search - initially all orders are valid candidates
        all_orders_valid = (1 << self.n) - 1
        search(0, 0, 0, 0, 0, all_orders_valid)

        # build final result
        selected_ids = [self.orders[i].id for i in best_selection[0]]
        total_weight = sum(weights[i] for i in best_selection[0])
        total_volume = sum(volumes[i] for i in best_selection[0])

        return selected_ids, best_payout[0], total_weight, total_volume


def optimize_load(truck: Truck, orders: List[Order]) -> Dict:
    """
    Entry point for the optimization.
    
    Takes a truck and list of orders, returns the best combination
    with utilization stats.
    """
    optimizer = LoadOptimizer(truck, orders)
    selected_ids, total_payout, total_weight, total_volume = optimizer.optimize()

    # calculate how full the truck is (as percentages)
    weight_util = 0.0
    volume_util = 0.0
    if truck.max_weight_lbs > 0:
        weight_util = (total_weight / truck.max_weight_lbs) * 100
    if truck.max_volume_cuft > 0:
        volume_util = (total_volume / truck.max_volume_cuft) * 100

    return {
        "truck_id": truck.id,
        "selected_order_ids": selected_ids,
        "total_payout_cents": total_payout,
        "total_weight_lbs": total_weight,
        "total_volume_cuft": total_volume,
        "utilization_weight_percent": round(weight_util, 2),
        "utilization_volume_percent": round(volume_util, 2),
    }
