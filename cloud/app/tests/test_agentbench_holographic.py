# ── Holographic Audit Cross-Validation (5 tests) ──


def test_holographic_expense_anomaly():
    """Expense anomaly: expense up + visit down + flow down -> expense_waste."""
    from cloud.app.compliance.holographic_audit import HolographicAuditEngine

    engine = HolographicAuditEngine()
    result = engine.check(
        expense_data=[{"expense": 500, "trend": "up"}],
        visit_data=[{"visit_count": 5, "trend": "down"}],
        distribution_data=[{"flow": 100, "trend": "down"}],
    )
    findings = [f.pattern for f in result.findings]
    assert "expense_waste" in findings


def test_holographic_visit_anomaly():
    """Visit anomaly: visits up but flow flat -> visit_fraud."""
    from cloud.app.compliance.holographic_audit import HolographicAuditEngine

    engine = HolographicAuditEngine()
    result = engine.check(
        expense_data=[],
        visit_data=[{"visit_count": 30, "trend": "up", "count": 25}],
        distribution_data=[{"flow": 200, "trend": "flat"}],
    )
    findings = [f.pattern for f in result.findings]
    assert "visit_fraud" in findings


def test_holographic_channel_stuffing():
    """Channel stuffing: cross-region distribution mismatch."""
    from cloud.app.compliance.holographic_audit import HolographicAuditEngine

    engine = HolographicAuditEngine()
    result = engine.check(
        expense_data=[],
        visit_data=[],
        distribution_data=[{"region": "north", "authorized_region": "south", "trend": "volatile"}],
    )
    findings = [f.pattern for f in result.findings]
    assert "channel_stuffing" in findings


def test_holographic_fake_activity():
    """Fake activity: expense and visits up but flow down."""
    from cloud.app.compliance.holographic_audit import HolographicAuditEngine

    engine = HolographicAuditEngine()
    result = engine.check(
        expense_data=[{"expense": 800, "trend": "up"}],
        visit_data=[{"visit_count": 40, "trend": "up"}],
        distribution_data=[{"flow": 50, "trend": "down"}],
    )
    findings = [f.pattern for f in result.findings]
    assert "fake_activity" in findings


def test_holographic_multi_evidence_backtrack():
    """Multi-evidence backtrack: verify correlated records are returned."""
    from cloud.app.compliance.holographic_audit import HolographicAuditEngine

    engine = HolographicAuditEngine()
    result = engine.check(
        expense_data=[{"expense": 300, "trend": "up", "rep_id": "R001"}],
        visit_data=[{"visit_count": 20, "trend": "up", "rep_id": "R001"}],
        distribution_data=[{"flow": 80, "trend": "down", "rep_id": "R001"}],
    )
    assert result.correlated_records is not None
    keys = result.correlated_records.keys()
    assert "expenses" in keys
    assert "visits" in keys
    assert "distributions" in keys
