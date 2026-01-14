import pytest
import time
import random
from datetime import date, timedelta
from app.models import Truck, Order
from app.optimizer import LoadOptimizer, optimize_load


class TestLoadOptimizer:
    """Unit tests for the LoadOptimizer class."""

    def test_empty_orders(self):
        """Test with no orders - should return empty selection."""
        truck = Truck(id="truck-1", max_weight_lbs=44000, max_volume_cuft=3000)
        result = optimize_load(truck, [])
        
        assert result["selected_order_ids"] == []
        assert result["total_payout_cents"] == 0
        assert result["total_weight_lbs"] == 0
        assert result["total_volume_cuft"] == 0

    def test_single_order_fits(self):
        """Test with single order that fits."""
        truck = Truck(id="truck-1", max_weight_lbs=44000, max_volume_cuft=3000)
        order = Order(
            id="ord-1",
            payout_cents=100000,
            weight_lbs=20000,
            volume_cuft=1500,
            origin="LA",
            destination="Dallas",
            pickup_date=date(2025, 12, 1),
            delivery_date=date(2025, 12, 5),
            is_hazmat=False
        )
        result = optimize_load(truck, [order])
        
        assert result["selected_order_ids"] == ["ord-1"]
        assert result["total_payout_cents"] == 100000

    def test_single_order_exceeds_weight(self):
        """Test with single order that exceeds weight capacity."""
        truck = Truck(id="truck-1", max_weight_lbs=10000, max_volume_cuft=3000)
        order = Order(
            id="ord-1",
            payout_cents=100000,
            weight_lbs=20000,
            volume_cuft=1500,
            origin="LA",
            destination="Dallas",
            pickup_date=date(2025, 12, 1),
            delivery_date=date(2025, 12, 5),
            is_hazmat=False
        )
        result = optimize_load(truck, [order])
        
        assert result["selected_order_ids"] == []
        assert result["total_payout_cents"] == 0

    def test_single_order_exceeds_volume(self):
        """Test with single order that exceeds volume capacity."""
        truck = Truck(id="truck-1", max_weight_lbs=44000, max_volume_cuft=1000)
        order = Order(
            id="ord-1",
            payout_cents=100000,
            weight_lbs=20000,
            volume_cuft=1500,
            origin="LA",
            destination="Dallas",
            pickup_date=date(2025, 12, 1),
            delivery_date=date(2025, 12, 5),
            is_hazmat=False
        )
        result = optimize_load(truck, [order])
        
        assert result["selected_order_ids"] == []
        assert result["total_payout_cents"] == 0

    def test_hazmat_isolation(self):
        """Test that hazmat orders are not combined with non-hazmat."""
        truck = Truck(id="truck-1", max_weight_lbs=44000, max_volume_cuft=3000)
        orders = [
            Order(
                id="ord-1",
                payout_cents=100000,
                weight_lbs=10000,
                volume_cuft=500,
                origin="LA",
                destination="Dallas",
                pickup_date=date(2025, 12, 1),
                delivery_date=date(2025, 12, 5),
                is_hazmat=False
            ),
            Order(
                id="ord-2",
                payout_cents=150000,
                weight_lbs=10000,
                volume_cuft=500,
                origin="LA",
                destination="Dallas",
                pickup_date=date(2025, 12, 1),
                delivery_date=date(2025, 12, 5),
                is_hazmat=True
            ),
        ]
        result = optimize_load(truck, orders)
        
        # Should select the higher paying hazmat order alone
        assert result["selected_order_ids"] == ["ord-2"]
        assert result["total_payout_cents"] == 150000

    def test_route_compatibility(self):
        """Test that orders with different routes are not combined."""
        truck = Truck(id="truck-1", max_weight_lbs=44000, max_volume_cuft=3000)
        orders = [
            Order(
                id="ord-1",
                payout_cents=100000,
                weight_lbs=10000,
                volume_cuft=500,
                origin="LA",
                destination="Dallas",
                pickup_date=date(2025, 12, 1),
                delivery_date=date(2025, 12, 5),
                is_hazmat=False
            ),
            Order(
                id="ord-2",
                payout_cents=90000,
                weight_lbs=10000,
                volume_cuft=500,
                origin="LA",
                destination="Houston",  # Different destination
                pickup_date=date(2025, 12, 1),
                delivery_date=date(2025, 12, 5),
                is_hazmat=False
            ),
        ]
        result = optimize_load(truck, orders)
        
        # Should select only ord-1 (higher payout, can't combine)
        assert result["selected_order_ids"] == ["ord-1"]
        assert result["total_payout_cents"] == 100000

    def test_time_window_conflict(self):
        """Test that orders with non-overlapping time windows are not combined."""
        truck = Truck(id="truck-1", max_weight_lbs=44000, max_volume_cuft=3000)
        orders = [
            Order(
                id="ord-1",
                payout_cents=100000,
                weight_lbs=10000,
                volume_cuft=500,
                origin="LA",
                destination="Dallas",
                pickup_date=date(2025, 12, 1),
                delivery_date=date(2025, 12, 3),
                is_hazmat=False
            ),
            Order(
                id="ord-2",
                payout_cents=90000,
                weight_lbs=10000,
                volume_cuft=500,
                origin="LA",
                destination="Dallas",
                pickup_date=date(2025, 12, 5),  # Pickup after ord-1 delivery
                delivery_date=date(2025, 12, 7),
                is_hazmat=False
            ),
        ]
        result = optimize_load(truck, orders)
        
        # Should select only ord-1 (time windows don't overlap)
        assert result["selected_order_ids"] == ["ord-1"]
        assert result["total_payout_cents"] == 100000

    def test_multiple_compatible_orders(self):
        """Test combining multiple compatible orders."""
        truck = Truck(id="truck-1", max_weight_lbs=44000, max_volume_cuft=3000)
        orders = [
            Order(
                id="ord-1",
                payout_cents=100000,
                weight_lbs=10000,
                volume_cuft=500,
                origin="LA",
                destination="Dallas",
                pickup_date=date(2025, 12, 1),
                delivery_date=date(2025, 12, 5),
                is_hazmat=False
            ),
            Order(
                id="ord-2",
                payout_cents=90000,
                weight_lbs=10000,
                volume_cuft=500,
                origin="LA",
                destination="Dallas",
                pickup_date=date(2025, 12, 2),
                delivery_date=date(2025, 12, 4),
                is_hazmat=False
            ),
            Order(
                id="ord-3",
                payout_cents=80000,
                weight_lbs=10000,
                volume_cuft=500,
                origin="LA",
                destination="Dallas",
                pickup_date=date(2025, 12, 2),
                delivery_date=date(2025, 12, 4),
                is_hazmat=False
            ),
        ]
        result = optimize_load(truck, orders)
        
        # Should select all three orders
        assert set(result["selected_order_ids"]) == {"ord-1", "ord-2", "ord-3"}
        assert result["total_payout_cents"] == 270000
        assert result["total_weight_lbs"] == 30000
        assert result["total_volume_cuft"] == 1500

    def test_sample_request(self):
        """Test the sample request from the problem statement."""
        truck = Truck(id="truck-123", max_weight_lbs=44000, max_volume_cuft=3000)
        orders = [
            Order(
                id="ord-001",
                payout_cents=250000,
                weight_lbs=18000,
                volume_cuft=1200,
                origin="Los Angeles, CA",
                destination="Dallas, TX",
                pickup_date=date(2025, 12, 5),
                delivery_date=date(2025, 12, 9),
                is_hazmat=False
            ),
            Order(
                id="ord-002",
                payout_cents=180000,
                weight_lbs=12000,
                volume_cuft=900,
                origin="Los Angeles, CA",
                destination="Dallas, TX",
                pickup_date=date(2025, 12, 4),
                delivery_date=date(2025, 12, 10),
                is_hazmat=False
            ),
            Order(
                id="ord-003",
                payout_cents=320000,
                weight_lbs=30000,
                volume_cuft=1800,
                origin="Los Angeles, CA",
                destination="Dallas, TX",
                pickup_date=date(2025, 12, 6),
                delivery_date=date(2025, 12, 8),
                is_hazmat=True
            ),
        ]
        result = optimize_load(truck, orders)
        
        # ord-001 + ord-002 = 430000 cents, which is > ord-003 alone (320000)
        # ord-003 is hazmat, can't combine with others
        assert set(result["selected_order_ids"]) == {"ord-001", "ord-002"}
        assert result["total_payout_cents"] == 430000
        assert result["total_weight_lbs"] == 30000
        assert result["total_volume_cuft"] == 2100
        assert abs(result["utilization_weight_percent"] - 68.18) < 0.01
        assert result["utilization_volume_percent"] == 70.0

    def test_performance_22_orders(self):
        """Test performance with 22 orders (worst case) - must complete in < 2 seconds."""
        truck = Truck(id="truck-1", max_weight_lbs=100000, max_volume_cuft=10000)
        
        # Generate 22 random orders with same route
        orders = []
        for i in range(22):
            orders.append(Order(
                id=f"ord-{i:03d}",
                payout_cents=random.randint(50000, 500000),
                weight_lbs=random.randint(1000, 5000),
                volume_cuft=random.randint(100, 500),
                origin="LA",
                destination="Dallas",
                pickup_date=date(2025, 12, 1),
                delivery_date=date(2025, 12, 10),
                is_hazmat=False
            ))
        
        start_time = time.time()
        result = optimize_load(truck, orders)
        elapsed_time = time.time() - start_time
        
        # Must complete in less than 2 seconds
        assert elapsed_time < 2.0, f"Performance test failed: took {elapsed_time:.2f}s"
        
        # Verify result is valid
        assert result["total_weight_lbs"] <= truck.max_weight_lbs
        assert result["total_volume_cuft"] <= truck.max_volume_cuft
        print(f"22-order optimization completed in {elapsed_time:.3f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
