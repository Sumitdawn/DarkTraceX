from darktracex.modules import phone, email, domain, ip, username, organization


def test_phone_module_returns_result():
    result = phone.run_phone_intel("+14158586273")
    assert result.findings
    assert result.timeline


def test_email_module_handles_value():
    result = email.run_email_intel("test@example.com")
    assert result.findings
    assert result.timeline


def test_domain_module_handles_value():
    result = domain.run_domain_intel("example.com")
    assert result.findings
    assert result.timeline


def test_ip_module_handles_value():
    result = ip.run_ip_intel("8.8.8.8")
    assert result.findings
    assert result.timeline


def test_username_module_handles_value():
    result = username.run_username_intel("admin")
    assert result.findings
    assert result.timeline


def test_organization_module_handles_value():
    result = organization.run_org_intel("Example Organization")
    assert result.findings
    assert result.timeline
