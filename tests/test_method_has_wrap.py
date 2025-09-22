from common.common_util import method_has_wrap

def test_method_has_wrap_positive():
    report = {
        'wrap_coexistence': [
            {'class':'A','method':'m','mods':['X'],'wrap_count':1,'occurrences':[]}
        ],
        'replace_wrap_coexistence': []
    }
    assert method_has_wrap(report,'A','m') is True

def test_method_has_wrap_negative():
    report = {
        'wrap_coexistence': [],
        'replace_wrap_coexistence': []
    }
    assert method_has_wrap(report,'A','m') is False


def test_method_has_wrap_replace_wrap():
    report = {
        'wrap_coexistence': [],
        'replace_wrap_coexistence': [
            {'class':'B','method':'n','mods':['X','Y'],'wrap_count':1,'occurrences':[]}
        ]
    }
    assert method_has_wrap(report,'B','n') is True
