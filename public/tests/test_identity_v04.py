import pytest
from garminai_public.identity import DemoIdentityVerifier, VerifiedPrincipal
from garminai_public.tenant_db import TenantActivityDB

SECRET=b'unit-test-only-secret-string-32-bytes-long!'
def verifier(now=10000):return DemoIdentityVerifier(SECRET,clock=lambda:now)
def principal(subject):
    v=verifier()
    return v.verify(v.issue_for_test(subject))

def test_signature_identity_and_audience():
    v=verifier(); t=v.issue_for_test('runner-a')
    assert v.verify(t).subject=='runner-a'
    with pytest.raises(PermissionError):v.verify(t+'x')
    with pytest.raises(PermissionError):DemoIdentityVerifier(SECRET,audience='other',clock=lambda:10000).verify(t)
    with pytest.raises(PermissionError):verifier(10301).verify(t)
    with pytest.raises(PermissionError):VerifiedPrincipal('runner-a',None)

def test_no_unverified_access():
    db=TenantActivityDB()
    for p in ('runner-a',None,{'subject':'runner-a'}):
        with pytest.raises(PermissionError):db.list(p)
    db.close()

def test_two_users_same_activity_id_isolated():
    a,b=principal('runner-a'),principal('runner-b')
    db=TenantActivityDB()
    db.upsert(a,'run-42',{'km':10})
    db.upsert(b,'run-42',{'km':7})
    assert db.get(a,'run-42')=={'km':10}
    assert db.get(b,'run-42')=={'km':7}
    assert db.list(a)==[{'activity_id':'run-42','data':{'km':10}}]
    assert db.list(b)==[{'activity_id':'run-42','data':{'km':7}}]
    assert db.delete(a,'run-42') is True
    assert db.get(b,'run-42')=={'km':7}
    assert db.get(a,'run-42') is None
    db.close()

def test_deletion_is_scoped_and_no_cross_tenant_updates():
    a,b=principal('runner-a'),principal('runner-b')
    db=TenantActivityDB()
    db.upsert(a,'1',{'km':1})
    db.upsert(a,'2',{'km':2})
    db.upsert(b,'1',{'km':99})
    assert db.delete_all_for_principal(a)==2
    assert db.list(a)==[]
    assert db.get(b,'1')=={'km':99}
    assert db.delete(a,'1') is False
    db.close()

def test_input_validation_and_copy():
    db=TenantActivityDB();a=principal('a')
    source={'nested':{'km':4}}
    db.upsert(a,'abc',source)
    source['nested']['km']=55
    record=db.get(a,'abc')
    record['nested']['km']=66
    assert db.get(a,'abc')=={'nested':{'km':4}}
    with pytest.raises(ValueError):db.upsert(a,'',{})
    with pytest.raises(ValueError):db.list(a,999)
    db.close()

def test_invalid_secret_and_subject():
    with pytest.raises(ValueError):DemoIdentityVerifier(b'short')
    with pytest.raises(ValueError):verifier().issue_for_test('a b')
