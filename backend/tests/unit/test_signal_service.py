"""Signal service and model import smoke test."""


def test_signal_models_importable():
    from dhanradar.signal.models import SignalRules, SignalDipFund
    from dhanradar.signal.models import SignalDeployment, SignalJournal
    assert SignalRules.__tablename__ == "signal_rules"
    assert SignalDipFund.__tablename__ == "signal_dip_fund"
    assert SignalDeployment.__tablename__ == "signal_deployments"
    assert SignalJournal.__tablename__ == "signal_journal"
