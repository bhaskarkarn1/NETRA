"""
NETRA Geospatial Intelligence — Indian City/State Geocoding

Contains coordinate data for major Indian cities, states, and UTs.
Used for mapping scam origin locations to the geospatial heat map.
This is a deterministic local lookup — no external API dependency.

Data source: Census of India 2011 + known cybercrime hotspot mapping.
"""

# Major Indian cities/states with coordinates
# Format: { "normalized_name": (latitude, longitude, state, is_hotspot) }
INDIA_GEOCODE: dict[str, tuple[float, float, str, bool]] = {
    # ---- Known Cybercrime Hotspots ----
    "jamtara": (23.9573, 86.7930, "Jharkhand", True),
    "deoghar": (24.4764, 86.6942, "Jharkhand", True),
    "giridih": (24.1900, 86.3000, "Jharkhand", True),
    "mewat": (27.9400, 77.0100, "Haryana", True),
    "nuh": (27.9400, 77.0100, "Haryana", True),
    "bharatpur": (27.2152, 77.5030, "Rajasthan", True),
    "mathura": (27.4924, 77.6737, "Uttar Pradesh", True),
    "alwar": (27.5530, 76.6346, "Rajasthan", True),

    # ---- Metro Cities ----
    "mumbai": (19.0760, 72.8777, "Maharashtra", False),
    "delhi": (28.7041, 77.1025, "Delhi", False),
    "new delhi": (28.6139, 77.2090, "Delhi", False),
    "bangalore": (12.9716, 77.5946, "Karnataka", False),
    "bengaluru": (12.9716, 77.5946, "Karnataka", False),
    "hyderabad": (17.3850, 78.4867, "Telangana", False),
    "chennai": (13.0827, 80.2707, "Tamil Nadu", False),
    "kolkata": (22.5726, 88.3639, "West Bengal", False),
    "pune": (18.5204, 73.8567, "Maharashtra", False),
    "ahmedabad": (23.0225, 72.5714, "Gujarat", False),
    "jaipur": (26.9124, 75.7873, "Rajasthan", False),
    "lucknow": (26.8467, 80.9462, "Uttar Pradesh", False),
    "surat": (21.1702, 72.8311, "Gujarat", False),
    "nagpur": (21.1458, 79.0882, "Maharashtra", False),
    "indore": (22.7196, 75.8577, "Madhya Pradesh", False),
    "bhopal": (23.2599, 77.4126, "Madhya Pradesh", False),
    "patna": (25.6093, 85.1376, "Bihar", False),
    "vadodara": (22.3072, 73.1812, "Gujarat", False),
    "ghaziabad": (28.6692, 77.4538, "Uttar Pradesh", False),
    "noida": (28.5355, 77.3910, "Uttar Pradesh", False),
    "gurugram": (28.4595, 77.0266, "Haryana", False),
    "gurgaon": (28.4595, 77.0266, "Haryana", False),
    "chandigarh": (30.7333, 76.7794, "Chandigarh", False),
    "coimbatore": (11.0168, 76.9558, "Tamil Nadu", False),
    "kochi": (9.9312, 76.2673, "Kerala", False),
    "cochin": (9.9312, 76.2673, "Kerala", False),
    "thiruvananthapuram": (8.5241, 76.9366, "Kerala", False),
    "trivandrum": (8.5241, 76.9366, "Kerala", False),
    "visakhapatnam": (17.6868, 83.2185, "Andhra Pradesh", False),
    "vizag": (17.6868, 83.2185, "Andhra Pradesh", False),
    "ranchi": (23.3441, 85.3096, "Jharkhand", False),
    "bhubaneswar": (20.2961, 85.8245, "Odisha", False),
    "guwahati": (26.1445, 91.7362, "Assam", False),
    "dehradun": (30.3165, 78.0322, "Uttarakhand", False),
    "shimla": (31.1048, 77.1734, "Himachal Pradesh", False),
    "srinagar": (34.0837, 74.7973, "Jammu & Kashmir", False),
    "jammu": (32.7266, 74.8570, "Jammu & Kashmir", False),
    "amritsar": (31.6340, 74.8723, "Punjab", False),
    "ludhiana": (30.9010, 75.8573, "Punjab", False),
    "varanasi": (25.3176, 82.9739, "Uttar Pradesh", False),
    "agra": (27.1767, 78.0081, "Uttar Pradesh", False),
    "kanpur": (26.4499, 80.3319, "Uttar Pradesh", False),
    "prayagraj": (25.4358, 81.8463, "Uttar Pradesh", False),
    "allahabad": (25.4358, 81.8463, "Uttar Pradesh", False),
    "meerut": (28.9845, 77.7064, "Uttar Pradesh", False),
    "raipur": (21.2514, 81.6296, "Chhattisgarh", False),
    "mangalore": (12.9141, 74.8560, "Karnataka", False),
    "mysore": (12.2958, 76.6394, "Karnataka", False),
    "mysuru": (12.2958, 76.6394, "Karnataka", False),
    "thane": (19.2183, 72.9781, "Maharashtra", False),
    "navi mumbai": (19.0330, 73.0297, "Maharashtra", False),

    # ---- State Names (capital coordinates) ----
    "jharkhand": (23.6102, 85.2799, "Jharkhand", True),
    "haryana": (29.0588, 76.0856, "Haryana", True),
    "rajasthan": (27.0238, 74.2179, "Rajasthan", True),
    "uttar pradesh": (26.8467, 80.9462, "Uttar Pradesh", True),
    "maharashtra": (19.7515, 75.7139, "Maharashtra", False),
    "karnataka": (15.3173, 75.7139, "Karnataka", False),
    "tamil nadu": (11.1271, 78.6569, "Tamil Nadu", False),
    "telangana": (18.1124, 79.0193, "Telangana", False),
    "andhra pradesh": (15.9129, 79.7400, "Andhra Pradesh", False),
    "west bengal": (22.9868, 87.8550, "West Bengal", False),
    "gujarat": (22.2587, 71.1924, "Gujarat", False),
    "madhya pradesh": (22.9734, 78.6569, "Madhya Pradesh", False),
    "kerala": (10.8505, 76.2711, "Kerala", False),
    "odisha": (20.9517, 85.0985, "Odisha", False),
    "assam": (26.2006, 92.9376, "Assam", False),
    "punjab": (31.1471, 75.3412, "Punjab", False),
    "bihar": (25.0961, 85.3131, "Bihar", False),
    "chhattisgarh": (21.2787, 81.8661, "Chhattisgarh", False),
    "uttarakhand": (30.0668, 79.0193, "Uttarakhand", False),
    "himachal pradesh": (31.1048, 77.1734, "Himachal Pradesh", False),
    "goa": (15.2993, 74.1240, "Goa", False),
    "tripura": (23.9408, 91.9882, "Tripura", False),
    "meghalaya": (25.4670, 91.3662, "Meghalaya", False),
    "manipur": (24.6637, 93.9063, "Manipur", False),
    "nagaland": (26.1584, 94.5624, "Nagaland", False),
    "mizoram": (23.1645, 92.9376, "Mizoram", False),
    "arunachal pradesh": (28.2180, 94.7278, "Arunachal Pradesh", False),
    "sikkim": (27.5330, 88.5122, "Sikkim", False),
}


def geocode_location(location_text: str) -> dict | None:
    """
    Resolve a location name to coordinates using the local lookup table.
    Returns: { "lat": float, "lng": float, "state": str, "is_hotspot": bool } or None
    """
    if not location_text:
        return None

    normalized = location_text.strip().lower()

    # Direct match
    if normalized in INDIA_GEOCODE:
        lat, lng, state, hotspot = INDIA_GEOCODE[normalized]
        return {"lat": lat, "lng": lng, "state": state, "is_hotspot": hotspot, "matched": normalized}

    # Partial match — check if any key is a substring
    for key, (lat, lng, state, hotspot) in INDIA_GEOCODE.items():
        if key in normalized or normalized in key:
            return {"lat": lat, "lng": lng, "state": state, "is_hotspot": hotspot, "matched": key}

    return None


def geocode_locations_batch(locations: list[str]) -> list[dict]:
    """Geocode a batch of location strings, returning only successful matches."""
    results = []
    seen = set()
    for loc in locations:
        geo = geocode_location(loc)
        if geo and geo["matched"] not in seen:
            seen.add(geo["matched"])
            geo["original"] = loc
            results.append(geo)
    return results
