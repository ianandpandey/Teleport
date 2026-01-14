# SmartLoad Optimization API

SmartLoad Optimization API is a stateless microservice that selects the most profitable
combination of shipment orders for a truck while respecting weight, volume, route,
hazmat, and time-window constraints.

This service is designed as part of a take-home assignment to demonstrate
real-world backend service design and optimization logic.

---

## Tech Stack

- Python 3
- FastAPI
- Docker & Docker Compose
- In-memory computation (no database)

---

## Features

- Maximizes total payout to carrier
- Respects truck weight and volume limits
- Ensures route compatibility (same origin & destination)
- Handles hazmat compatibility
- Considers pickup and delivery time windows
- Stateless and fast (works for up to 22 orders)

---

## How to Run

### Prerequisites
- Docker
- Docker Compose

### Steps

```bash
git clone https://github.com/ianandpandey/Teleport.git
cd Teleport
docker compose up --build
