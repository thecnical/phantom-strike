# 🔒 Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.0.x   | ✅ Full Support    |
| 1.0.x   | ⚠️ Limited Support |
| < 1.0   | ❌ Not Supported   |

## Reporting a Vulnerability

**⚠️ IMPORTANT: Do NOT create public GitHub issues for security vulnerabilities!**

### Responsible Disclosure Process

1. **Email us directly**: security@phantomstrike.dev
   - Include detailed description
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

2. **Encryption (Optional)**: 
   - PGP Key: [security@phantomstrike.dev.asc](https://phantomstrike.dev/security-key.asc)
   - Fingerprint: `A1B2 C3D4 E5F6 7890 1234 5678 90AB CDEF 1234 5678`

3. **Response Timeline**:
   - Acknowledgment: Within 24 hours
   - Initial assessment: Within 72 hours
   - Fix timeline: Based on severity
   - Public disclosure: After fix is released

### Severity Classification

| Severity | Description | Response Time |
|:---------|:------------|:-------------:|
| 🔴 Critical | RCE, SQLi, Auth Bypass | 24 hours |
| 🟠 High | XSS, Data Exposure | 72 hours |
| 🟡 Medium | CSRF, Info Disclosure | 1 week |
| 🟢 Low | Best practices | 1 month |

## Security Best Practices for Users

### When Using PhantomStrike

✅ **DO:**
- Only test systems you own or have written authorization for
- Use isolated environments for testing
- Keep API keys secure (use environment variables)
- Follow responsible disclosure for found vulnerabilities
- Update to latest version regularly

❌ **DON'T:**
- Test production systems without approval
- Share API keys in public repositories
- Use for illegal activities
- Attack systems you don't have permission to test

### API Key Security

```bash
# ✅ Good: Use environment variables
export GROQ_API_KEY="your-key-here"

# ❌ Bad: Never hardcode keys
GROQ_API_KEY = "gsk_123456..."  # Don't do this!
```

### Running Safely

```bash
# Use Docker for isolation
docker run --rm -e GROQ_API_KEY=$GROQ_API_KEY phantom-strike

# Or use virtual environments
python -m venv venv
source venv/bin/activate
```

## Known Security Considerations

### Current Status

- ✅ All network calls use HTTPS
- ✅ No credential storage in logs
- ✅ API keys not logged
- ✅ Scan results isolated per session
- ⚠️ Tool itself requires careful use (see disclaimer)

### Ongoing Security Work

- [ ] Implement request signing for C2 agents
- [ ] Add audit logging for compliance
- [ ] Implement role-based access control (RBAC)
- [ ] Add scan result encryption at rest

## Hall of Fame

We thank these security researchers for responsible disclosures:

| Name | Finding | Date |
|:-----|:--------|:-----|
| *Waiting for first disclosure* | - | - |

## Security Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [MITRE ATT&CK Framework](https://attack.mitre.org/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

## Contact

- **Security Team**: chandanabhay4456@gmail.com
- **Project Lead**: chandanabhay4456@gmail.com

---

**Remember: With great power comes great responsibility. Use PhantomStrike ethically and legally.**
