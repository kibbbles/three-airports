# EDA helper functions — reusable transforms and lookups

AIRLINE_NAMES = {
    "AA": "American Airlines",
    "AS": "Alaska Airlines",
    "B6": "JetBlue Airways",
    "DL": "Delta Air Lines",
    "F9": "Frontier Airlines",
    "G4": "Allegiant Air",
    "HA": "Hawaiian Airlines",
    "MQ": "Envoy Air (American Eagle)",
    "NK": "Spirit Airlines",
    "OH": "PSA Airlines (American Eagle)",
    "OO": "SkyWest Airlines",
    "PT": "Piedmont Airlines (American Eagle)",
    "QX": "Horizon Air",
    "UA": "United Airlines",
    "VX": "Virgin America",
    "WN": "Southwest Airlines",
    "YV": "Mesa Airlines",
    "YX": "Republic Airways",
    "9E": "Endeavor Air (Delta Connection)",
    "EV": "ExpressJet Airlines",
}


def map_airline(df, code_col="Reporting_Airline", name_col="Airline"):
    """Add a human-readable airline name column next to the carrier code column."""
    df = df.copy()
    df[name_col] = df[code_col].map(AIRLINE_NAMES).fillna(df[code_col])
    return df
