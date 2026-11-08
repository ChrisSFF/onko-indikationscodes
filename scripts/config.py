"""Which drugs count as oncology / haematology.

Filter is by ATC code prefix. The oncology team should review this list once;
anything not matched here is still visible on the page under "Alle".
"""

BAG_URL = (
    "https://epl.bag.admin.ch/static/sl/publication/fhir/"
    "foph-sl-publication-latest-de.ndjson"
)

# (ATC prefix, group label). First matching prefix wins, so put specific
# exclusions (label None) before the broader prefix they belong to.
ATC_GROUPS = [
    # --- Onkologie ---
    ("L01", "Onkologie – Antineoplastika"),
    ("L02", "Onkologie – Endokrine Tumortherapie"),
    ("V10", "Onkologie – Radiopharmaka"),
    ("H01CB", "Onkologie – Somatostatin-Analoga (NET)"),
    ("M05BX04", "Onkologie – Supportiv (Denosumab)"),
    ("V03AF", "Onkologie – Supportiv (Entgiftung Zytostatika)"),
    ("A04AD", "Onkologie – Supportiv (Antiemetika)"),
    # --- Immunmodulatoren, nur onko/häma-relevante Untergruppen ---
    ("L03AA", "Hämatologie – Wachstumsfaktoren (G-CSF)"),
    ("L03AB07", None),  # Interferon beta (MS) – ausgeschlossen
    ("L03AB08", None),  # Interferon beta (MS) – ausgeschlossen
    ("L03AB13", None),  # Peginterferon beta (MS) – ausgeschlossen
    ("L03AB", "Hämatologie/Onkologie – Interferone"),
    ("L03AX", "Onkologie – Immunstimulanzien"),
    ("L04AX", "Hämatologie – Immunmodulatoren (IMiDs)"),
    ("L04AJ", "Hämatologie – Komplementinhibitoren"),
    # --- Hämatologie ---
    # B01 (Antithrombotika) bewusst nicht: fast nur Kardiologie (z.B. Ticagrelor).
    ("B02", "Hämatologie – Hämostatika / Gerinnungsfaktoren"),
    ("B03", "Hämatologie – Antianämika"),
    ("B06", "Hämatologie – Andere Hämatologika"),
]


def group_for_atc(atc: str):
    atc = (atc or "").upper()
    for prefix, label in ATC_GROUPS:
        if atc.startswith(prefix):
            return label
    return None
