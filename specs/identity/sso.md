---
id: REQ-IAM-001
title: Single Sign-On (SSO) Support
status: active
priority: high
tags: [identity, security, enterprise]
---

# Single Sign-On (SSO) Support

Enterprise customers require the ability to manage access to the application using their existing Identity Providers (IdP).

## Requirements

1. **Protocol Support**: The system MUST support SAML 2.0 and OpenID Connect (OIDC) protocols.
2. **Just-In-Time Provisioning**: The system MUST support creating users automatically on first login if JIT provisioning is enabled for the tenant.
3. **IdP Configuration**: Tenant administrators MUST be able to configure SSO settings (e.g., IdP URL, x509 certificate) independently from a self-serve dashboard.
4. **Enforcement**: If "Strict SSO" is enabled for a tenant, users MUST NOT be able to log in using standard email/password credentials.
