# Investment Research Quality Gates

Quality gates specific to investment research that ensure data recency, balanced analysis, proper risk disclosure, and appropriate caveats for paper trading education.

**CRITICAL**: All investment research must include the mandatory disclaimer:
> "This is research synthesis, NOT financial advice. Past performance does not guarantee future results. Never invest more than you can afford to lose."

---

## Gate 1: Source Recency Check

### Criteria
Investment data has strict freshness requirements based on use case.

### Recency Thresholds
```python
RECENCY_THRESHOLDS = {
    "trading_decisions": {
        "max_age_hours": 24,
        "warning_age_hours": 12,
        "description": "Real-time trading data"
    },
    "investment_research": {
        "max_age_days": 7,
        "warning_age_days": 3,
        "description": "General investment analysis"
    },
    "fundamental_analysis": {
        "max_age_days": 90,
        "warning_age_days": 30,
        "description": "Financial statements and SEC filings"
    },
    "market_overview": {
        "max_age_days": 1,
        "warning_age_hours": 4,
        "description": "Market conditions and sentiment"
    }
}
```

### Validation Function
```python
def check_source_recency(data_timestamp, use_case):
    threshold = RECENCY_THRESHOLDS.get(use_case, RECENCY_THRESHOLDS["investment_research"])

    age = datetime.now() - data_timestamp

    if use_case in ["trading_decisions", "market_overview"]:
        max_age = timedelta(hours=threshold["max_age_hours"])
        warning_age = timedelta(hours=threshold["warning_age_hours"])
    else:
        max_age = timedelta(days=threshold["max_age_days"])
        warning_age = timedelta(days=threshold["warning_age_days"])

    if age > max_age:
        return {"status": "fail", "message": f"Data too old: {age}"}
    elif age > warning_age:
        return {"status": "warning", "message": f"Data aging: {age}"}
    else:
        return {"status": "pass", "message": f"Data fresh: {age}"}
```

### Pass/Fail Thresholds
- **Pass**: Data within acceptable age for use case
- **Warning**: Data aging but still usable with caveat
- **Fail**: Data too old for reliable analysis

### Actions
- **Pass**: Use data with confidence
- **Warning**: Include data age warning in output
- **Fail**: Flag as stale, attempt to refresh, or decline to provide analysis

---

## Gate 2: Confirmation Bias Check

### Criteria
All investment analysis MUST include both bullish AND bearish perspectives to avoid confirmation bias.

### Requirements
```python
CONFIRMATION_BIAS_REQUIREMENTS = {
    "require_bull_case": True,
    "require_bear_case": True,
    "min_opposing_sources": 2,
    "flag_one_sided_analysis": True,
    "required_sections": [
        "bull_case",
        "bear_case",
        "key_risks",
        "counterarguments"
    ]
}
```

### Validation Function
```python
def check_confirmation_bias(analysis):
    checks = {
        "has_bull_case": False,
        "has_bear_case": False,
        "has_risk_section": False,
        "opposing_sources": 0,
        "balanced": False
    }

    # Check for required sections
    if "bull case" in analysis.lower() or "bullish" in analysis.lower():
        checks["has_bull_case"] = True

    if "bear case" in analysis.lower() or "bearish" in analysis.lower():
        checks["has_bear_case"] = True

    if "risk" in analysis.lower():
        checks["has_risk_section"] = True

    # Count opposing viewpoints
    checks["opposing_sources"] = count_opposing_viewpoints(analysis)

    # Determine if balanced
    checks["balanced"] = (
        checks["has_bull_case"] and
        checks["has_bear_case"] and
        checks["has_risk_section"] and
        checks["opposing_sources"] >= 2
    )

    return checks
```

### Pass/Fail Thresholds
- **Pass**: All required sections present, balanced analysis
- **Warning**: Missing one perspective or insufficient opposing sources
- **Fail**: One-sided analysis without counterarguments

### Actions
- **Pass**: Analysis is balanced and objective
- **Warning**: Add missing perspective before publishing
- **Fail**: Reject analysis until both sides are represented

---

## Gate 3: Risk Disclosure Check

### Criteria
All investment outputs MUST include mandatory risk disclosures.

### Required Disclosures
```python
REQUIRED_DISCLOSURES = {
    "paper_trading_notice": {
        "text": "Paper trading mode is active - no real money involved.",
        "required": True
    },
    "not_financial_advice": {
        "text": "This is research synthesis, NOT financial advice.",
        "required": True
    },
    "past_performance_warning": {
        "text": "Past performance does not guarantee future results.",
        "required": True
    },
    "position_sizing_warning": {
        "text": "Never invest more than you can afford to lose.",
        "required": True
    },
    "volatility_warning": {
        "text": "[Asset type] can be highly volatile and speculative.",
        "required_for": ["crypto", "options", "penny_stocks"]
    }
}
```

### Validation Function
```python
def check_risk_disclosures(output, asset_type):
    missing_disclosures = []

    for key, disclosure in REQUIRED_DISCLOSURES.items():
        if disclosure.get("required", False):
            if disclosure["text"].lower() not in output.lower():
                missing_disclosures.append(key)
        elif asset_type in disclosure.get("required_for", []):
            if disclosure["text"].lower() not in output.lower():
                missing_disclosures.append(key)

    return {
        "status": "pass" if not missing_disclosures else "fail",
        "missing": missing_disclosures
    }
```

### Pass/Fail Thresholds
- **Pass**: All required disclosures present
- **Warning**: N/A - disclosures are mandatory
- **Fail**: Any required disclosure missing

### Actions
- **Pass**: Output is compliant
- **Fail**: Add missing disclosures before publishing

### Mandatory Disclaimer Block
Every investment output MUST include this block:
```markdown
---
**DISCLAIMER**: This is research synthesis, NOT financial advice.
Past performance does not guarantee future results.
Never invest more than you can afford to lose.
Paper trading mode is active - no real money involved.
---
```

---

## Gate 4: Liquidity Check

### Criteria
Verify that assets being analyzed have adequate trading liquidity.

### Liquidity Thresholds
```python
LIQUIDITY_THRESHOLDS = {
    "stocks": {
        "min_avg_volume": 100000,  # shares/day
        "min_market_cap": 10000000,  # $10M
        "warning_volume": 500000,
        "warning_market_cap": 100000000  # $100M
    },
    "crypto": {
        "min_24h_volume": 1000000,  # $1M
        "min_market_cap": 10000000,  # $10M
        "warning_volume": 10000000,  # $10M
        "warning_market_cap": 100000000  # $100M
    },
    "options": {
        "min_open_interest": 100,
        "min_daily_volume": 50,
        "warning_open_interest": 1000,
        "warning_daily_volume": 500
    }
}
```

### Validation Function
```python
def check_liquidity(asset_type, volume, market_cap=None, open_interest=None):
    thresholds = LIQUIDITY_THRESHOLDS.get(asset_type, LIQUIDITY_THRESHOLDS["stocks"])

    if asset_type == "options":
        if volume < thresholds["min_daily_volume"]:
            return {"status": "fail", "reason": "Insufficient options volume"}
        elif volume < thresholds["warning_daily_volume"]:
            return {"status": "warning", "reason": "Low options volume"}
    else:
        if volume < thresholds["min_avg_volume"]:
            return {"status": "fail", "reason": "Insufficient volume"}
        elif market_cap and market_cap < thresholds["min_market_cap"]:
            return {"status": "fail", "reason": "Market cap too small"}
        elif volume < thresholds["warning_volume"]:
            return {"status": "warning", "reason": "Low volume - wider spreads likely"}

    return {"status": "pass", "reason": "Adequate liquidity"}
```

### Pass/Fail Thresholds
- **Pass**: Volume and market cap above minimums
- **Warning**: Below warning thresholds but above minimums
- **Fail**: Below minimum thresholds

### Actions
- **Pass**: Proceed with analysis
- **Warning**: Include liquidity warning in output
- **Fail**: Flag as illiquid, warn about execution risk

---

## Gate 5: Backtesting Caveat Check

### Criteria
Any analysis involving historical patterns or backtested results MUST include appropriate caveats.

### Required Caveats
```python
BACKTESTING_CAVEATS = [
    "Backtested results do not guarantee future performance",
    "Past performance does not predict future results",
    "Slippage and trading fees not included in backtests",
    "Market conditions change over time",
    "Survivorship bias may affect historical analysis",
    "Curve fitting may overstate historical performance"
]
```

### Validation Function
```python
def check_backtesting_caveats(analysis):
    # Check if analysis contains backtesting/historical pattern claims
    backtesting_indicators = [
        "backtest",
        "historical pattern",
        "would have returned",
        "past X years",
        "historically",
        "pattern recognition"
    ]

    needs_caveats = any(
        indicator in analysis.lower()
        for indicator in backtesting_indicators
    )

    if not needs_caveats:
        return {"status": "pass", "reason": "No backtesting claims detected"}

    # Check for required caveats
    has_caveat = any(
        caveat.lower() in analysis.lower()
        for caveat in BACKTESTING_CAVEATS
    )

    if has_caveat:
        return {"status": "pass", "reason": "Backtesting caveats present"}
    else:
        return {"status": "fail", "reason": "Missing backtesting caveats"}
```

### Pass/Fail Thresholds
- **Pass**: No backtesting claims OR appropriate caveats included
- **Warning**: N/A
- **Fail**: Backtesting claims without caveats

### Actions
- **Pass**: Analysis is properly caveated
- **Fail**: Add required caveats before publishing

---

## Integrated Quality Gate Pipeline

### Pipeline Flow
```
Input: Investment Analysis Draft

1. Source Recency Check
   ├─ Pass → Continue
   ├─ Warning → Add age caveat, Continue
   └─ Fail → Flag stale data, request refresh

2. Confirmation Bias Check
   ├─ Pass → Continue
   ├─ Warning → Request additional perspective
   └─ Fail → Block until balanced

3. Risk Disclosure Check
   ├─ Pass → Continue
   └─ Fail → Add missing disclosures

4. Liquidity Check
   ├─ Pass → Continue
   ├─ Warning → Add liquidity warning
   └─ Fail → Add strong liquidity warning

5. Backtesting Caveat Check
   ├─ Pass → Continue
   └─ Fail → Add required caveats

Output: Validated Investment Analysis with all required elements
```

### Final Validation
```python
def validate_investment_analysis(analysis, metadata):
    """Run all quality gates on investment analysis."""

    results = {
        "recency": check_source_recency(
            metadata["data_timestamp"],
            metadata["use_case"]
        ),
        "confirmation_bias": check_confirmation_bias(analysis),
        "risk_disclosure": check_risk_disclosures(
            analysis,
            metadata["asset_type"]
        ),
        "liquidity": check_liquidity(
            metadata["asset_type"],
            metadata.get("volume", 0),
            metadata.get("market_cap", 0)
        ),
        "backtesting": check_backtesting_caveats(analysis)
    }

    # Determine overall status
    if any(r["status"] == "fail" for r in results.values()):
        overall = "fail"
    elif any(r["status"] == "warning" for r in results.values()):
        overall = "warning"
    else:
        overall = "pass"

    return {
        "overall": overall,
        "gates": results,
        "can_publish": overall != "fail"
    }
```

---

## Quality Gate Report Template

Include this section in investment outputs:

```markdown
### Quality Assessment

**Source Recency**: [Pass/Warning/Fail]
- Data timestamp: [DateTime]
- Age: [Hours/Days]
- Status: [Fresh / Aging / Stale]

**Confirmation Bias Check**: [Pass/Warning/Fail]
- Bull case included: [Yes/No]
- Bear case included: [Yes/No]
- Opposing sources: [Count]
- Status: [Balanced / One-sided]

**Risk Disclosures**: [Pass/Fail]
- Paper trading notice: [Present/Missing]
- Not financial advice: [Present/Missing]
- Past performance warning: [Present/Missing]
- Position sizing warning: [Present/Missing]

**Liquidity Check**: [Pass/Warning/Fail]
- Average volume: [X]
- Market cap: $[X]
- Status: [Adequate / Low / Insufficient]

**Backtesting Caveats**: [Pass/Fail]
- Historical claims: [Yes/No]
- Caveats present: [Yes/No]

**Overall Quality**: [Pass / Warning / Fail]
```

---

## Implementation Notes

These quality gates should be implemented in:
- `lib/investment-quality-gates.py` - Python module for gate execution
- Integration with `lib/research_synthesizer.py` - Apply gates during synthesis
- Integration with agents - Agents should self-check before output

Gates are configurable via `adapters/investment/adapter.yaml` under the `quality_gates` section.

### Enforcement Priority
1. **Risk Disclosure** - MANDATORY, no exceptions
2. **Confirmation Bias** - MANDATORY for published analysis
3. **Source Recency** - Important, warnings acceptable
4. **Liquidity Check** - Important for trading analysis
5. **Backtesting Caveats** - Required when applicable
