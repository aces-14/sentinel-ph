from src.model.risk_scorer import RiskScorer

s = RiskScorer.load()
dates = [
    "2019-08-01",  # PH rainy season peak — expect HIGH/MEDIUM
    "2019-11-01",  # tail of rainy season
    "2020-03-01",  # dry season — expect LOW/MEDIUM
    "2022-07-01",  # rainy season
    "2022-11-01",  # tail of rainy season
    "2023-02-01",  # dry season — expect LOW/MEDIUM
]
for d in dates:
    r = s.predict(d)
    print(f"{r['as_of_date']}  {r['risk_level']:<8}  {r['predicted_cases']:>6,} cases")
