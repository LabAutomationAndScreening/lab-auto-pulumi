# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

---

## [Unreleased]

### Added
- Describe new features added in this version.

### Changed
- Describe changes in existing functionality.

### Deprecated
- List features that are still available but will be removed in future versions.

### Removed
- List features that have been removed.

### Fixed
- List any bug fixes.

### Security
- Describe security fixes or improvements.

---
## [0.5.0] - 2026-09-30

### Added
- `SecurityGroupIngressRuleConfig` and `NewSecurityGroupConfig.ingress_rules`: `Ec2WithRdp` creates inbound rules
  on the classic `aws.vpc.SecurityGroupIngressRule` resource (`tcp` or `udp`, one of `source_security_group_id` or
  `cidr_ipv4`, description required). The egress-all rule is back on `aws.vpc.SecurityGroupEgressRule`.

### Changed
- A new security group (`NewSecurityGroupConfig`) is now the classic `aws.ec2.SecurityGroup` instead of the aws-native
  one. The classic resource revokes AWS's default allow-all egress rule on create, so the standalone egress-all rule
  no longer collides with it (`InvalidPermission.Duplicate`). It ignores changes to its inline `ingress`/`egress` so
  rules stay owned by the standalone resources. `Ec2WithRdp.security_group` is therefore the classic type for new
  groups; it stays the aws-native type for `ExistingSecurityGroupConfig`.

> [!WARNING]
> Upgrading replaces the security group created by `Ec2WithRdp`: Pulumi creates the new group, moves the instance
> to it in place, then deletes the old one. Anything outside the stack that references the old group's ID (rules in
> other security groups, other stacks) must be updated, or the old group's deletion fails while it is still in use.

---
## [0.4.0] - 2026-09-30

### Removed
- `Ec2WithRdp` no longer creates any `aws-native` `SecurityGroupIngress`/`SecurityGroupEgress` resources, and
  `NewSecurityGroupConfig.ingress_rules` is gone. The CloudFormation-backed rule resources silently adopt an
  existing identical rule instead of failing, so two Pulumi resources end up owning one AWS rule and deleting
  either one revokes it. This release is the transitional "no rules" step; the next release re-adds rules on
  the classic `aws.vpc.SecurityGroupIngressRule`/`SecurityGroupEgressRule` resources.

> [!WARNING]
> Stacks deployed with a version before 0.4.0 must deploy 0.4.0 before upgrading to any newer version. Skipping
> it fails the upgrade: the new rule resources collide with the still-existing `aws-native` rules.
>
> Deploying this release deletes the security group rules `Ec2WithRdp` previously managed (the configured ingress
> rules and the egress-all rule), which interrupts RDP and SSM access to the instance. Deploy this release first, deploy, bump to any version after this one and deploy again to restore connectivity. Do not create identical replacement rules before upgrading: the `aws-native` rule deletion revokes the
> matching AWS rule, removing your replacement along with it.

---
## [0.2.3] - 2026-05-05

### Added
- ORG_MANAGED_PARAMS_AND_SECRETS_PREFIX constant for consistent namespace for all managed secrets and ssm params.

### Deprecated
- ORG_MANAGED_SSM_PARAM_PREFIX has been deprecated in favor of ORG_MANAGED_PARAMS_AND_SECRETS_PREFIX. Value is same but name changed.

## [0.2.2] - Unreleased

CI Issue caused us to skip this version

## [0.2.1] - 2026-04-28

### Fixed
- Do not delete security groups on EC2 before replacement

---

## [0.1.18] - 2024-12-22

### Added
- Python 3.14 support

---

## [0.1.0] - 2024-12-18

### Added
- Project setup.
- Initial functionality implemented.

---

### How to Use This Changelog

- **Added:** For new features.
- **Changed:** For changes in existing functionality.
- **Deprecated:** For features that will soon be removed.
- **Removed:** For features that have been removed.
- **Fixed:** For bug fixes.
- **Security:** In case of vulnerabilities addressed.

---

### Versioning

This project uses **Semantic Versioning (MAJOR.MINOR.PATCH)**:
- **MAJOR:** Incompatible API changes.
- **MINOR:** Backward-compatible new features.
- **PATCH:** Backward-compatible bug fixes.

For example:
- `1.0.0`: Major release with breaking changes.
- `1.1.0`: New backward-compatible feature.
- `1.1.1`: Bug fix or minor change.

---

### Contributing to the Changelog

When contributing changes, ensure you update the `[Unreleased]` section of this file with a brief description of your contribution.

- Use clear, concise language.
- Categorize your change under **Added**, **Changed**, **Deprecated**, **Removed**, **Fixed**, or **Security**.

When releasing a new version:
1. Move changes from `[Unreleased]` to a new section with the version number and release date.
2. Update any relevant documentation if necessary.

---

Thank you for helping us maintain a clean and clear changelog! 🚀

<!--
============== WARNING ==============================================================================
File is managed by copier template: gh:LabAutomationAndScreening/copier-base-template.git
See .config/.copier-managed-files.json for details.

You are welcome to make changes to this file in your repo if they are custom to your project,
but if the change should be shared with other projects, please backport it to the template repo.
=====================================================================================================
-->
