from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
import json

print("Verfügbare Metriken:", faiss.METRIC_INNER_PRODUCT, faiss.METRIC_L2, faiss.METRIC_L1)


# Sample input from your example
offer_raw = {
    "after_two_years_cost_euros": 54.59,
    "installation_service": False,
    "connection_type": "Fiber",
    "monthly_cost_euros": 52.59,
    "product_id": "513",
    "voucher_type": "percentage",
    "tv_included": True,
    "voucher_value_euros": 0.07,
    "provider_name": "Byte Ultimate 130",
    "speed_mbps": 130,
    "contract_duration_months": 24
}

realistic_offers = [
    {
        "after_two_years_cost_euros": 49.99 * 24,
        "installation_service": False,
        "connection_type": "DSL",
        "monthly_cost_euros": 49.99,
        "product_id": "201",
        "voucher_type": "fixed",
        "tv_included": False,
        "voucher_value_euros": 50.0,
        "provider_name": "FastNet Basic 100",
        "speed_mbps": 100,
        "contract_duration_months": 24
    },
    {
        "after_two_years_cost_euros": 59.99 * 12 + 39.99 * 12,
        "installation_service": True,
        "connection_type": "Fiber",
        "monthly_cost_euros": 59.99,
        "product_id": "301",
        "voucher_type": "percentage",
        "tv_included": True,
        "voucher_value_euros": 10.0,
        "provider_name": "Speedy Plus 250",
        "speed_mbps": 250,
        "contract_duration_months": 24
    },
    {
        "after_two_years_cost_euros": 39.99 * 24,
        "installation_service": False,
        "connection_type": "DSL",
        "monthly_cost_euros": 39.99,
        "product_id": "101",
        "voucher_type": "fixed",
        "tv_included": False,
        "voucher_value_euros": 0.0,
        "provider_name": "BudgetNet 50",
        "speed_mbps": 50,
        "contract_duration_months": 24
    },
    {
        "after_two_years_cost_euros": 59.99 * 12 + 39.99 * 12,
        "installation_service": True,
        "connection_type": "Fiber",
        "monthly_cost_euros": 55.99,
        "product_id": "2342",
        "voucher_type": "absolute",
        "tv_included": True,
        "voucher_value_euros": 10.0,
        "provider_name": "Speedy Premium 250",
        "speed_mbps": 250,
        "contract_duration_months": 24
    },
    {
        "after_two_years_cost_euros": 59.99 * 12 + 39.99 * 12,
        "installation_service": True,
        "connection_type": "DSL",
        "monthly_cost_euros": 55.99,
        "product_id": "2342",
        "voucher_type": "absolute",
        "tv_included": True,
        "voucher_value_euros": 10.0,
        "provider_name": "Speedy Premium 250 1",
        "speed_mbps": 250,
        "contract_duration_months": 24
    },
    offer_raw  # dein ursprüngliches Beispiel
]

# Simple one-hot encoding for connection_type and voucher_type
connection_type_map = {"Fiber": 1, "DSL": 0}
voucher_type_map = {"percentage": 1, "fixed": 0}

# Normalization constants (can be adapted)
MAX_SPEED = 1000
MAX_COST = 100
MAX_CONTRACT = 36

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")

def vectorize_offer(offer):
    name_vec = model.encode(offer["provider_name"]) * 0.2  # (384,)

    numeric_vec = np.array([
        offer["speed_mbps"] / MAX_SPEED * 10.0,  # wichtig
        offer["monthly_cost_euros"] / MAX_COST * 2.0,  # ziemlich wichtig
        offer["after_two_years_cost_euros"] / (MAX_COST * 2) * 1.5,  # mittelwichtig
        offer["contract_duration_months"] / MAX_CONTRACT * 1.0,
        float(offer["tv_included"]) * 1.0,
        float(offer["installation_service"]) * 0.5,
        connection_type_map.get(offer["connection_type"], 0) * 1.0,
        voucher_type_map.get(offer["voucher_type"], 0) * 0.5,
        offer["voucher_value_euros"] / 100 * 0.5
    ])

    return np.concatenate([numeric_vec, name_vec])


vectors = np.array([vectorize_offer(o) for o in realistic_offers]).astype("float32")

index = faiss.IndexFlat(vectors.shape[1], faiss.METRIC_L1)
index.add(vectors)
print(vectors.dtype)  # float32




query_vec = vectorize_offer(offer_raw).astype("float32").reshape(1, -1)
print(query_vec.dtype)  # float32
print(vectors.shape[1])  # z.B. 25
print(query_vec.shape)  # sollte (1, 25) sein
assert not np.isnan(vectors).any()
assert not np.isinf(vectors).any()

D, I = index.search(query_vec, k=3)

for i, dist in zip(I[0], D[0]):
    print(f"Angebot #{i} mit L1-Distanz {dist:.4f}")