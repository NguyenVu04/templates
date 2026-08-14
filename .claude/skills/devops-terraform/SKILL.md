---
name: devops-terraform
description: >-
  Production-grade Terraform and infrastructure-as-code engineering: provisioning cloud resources,
  remote state management and locking, module design, environment layout (dev/staging/prod),
  import/refactor of existing infrastructure, and Terraform CI pipelines. Use this skill whenever the
  user mentions Terraform, IaC, infrastructure as code, `.tf` files, HCL, provisioning cloud
  resources, Terraform state, Terraform modules, or asks to "provision infra", write a Terraform
  module, set up remote state, or fix drift/plan issues — even if they don't say "Terraform"
  explicitly.
---

# Terraform & Infrastructure as Code

A skill for producing production-grade Terraform and making sound infrastructure-provisioning decisions. The core theme: **boring, reproducible, observable, and reversible**. Clever HCL is a liability; predictable HCL is an asset.

## Before writing any configuration

Establish (ask if not inferable):
- **Cloud provider(s) and target environment** — AWS/GCP/Azure, single account vs multi-account, which regions.
- **Scale reality** — a 3-person startup does not need a mega multi-account landing zone. Match complexity to actual need; recommend the simplest thing that works and note the upgrade path.
- **Existing conventions** — if the repo already has Terraform, read it first (module layout, naming, tagging conventions) and match its style rather than imposing a new one.

## Non-negotiables for any team/production usage

1. **Remote state with locking** — S3+DynamoDB (or S3 native locking in TF ≥1.10), GCS, Azure Blob, or Terraform Cloud. Local state = guaranteed eventual disaster (lost laptop, concurrent applies, secrets in plaintext on disk).
2. **State contains secrets in plaintext** — treat the state backend as a secret store: encrypt at rest, restrict access, never commit `terraform.tfstate` (gitignore it plus `.terraform/`). Never hardcode secrets in `.tf` files either — pull them from a secret manager or CI secret store.
3. **Pin versions** — `required_version` for Terraform, version constraints for every provider (`~> 5.0`), commit `.terraform.lock.hcl`.
4. **Plan before apply, always** — in CI: `plan` on PR (posted as comment), `apply` only on merge to main, from the saved plan artifact (`terraform apply tfplan`) so what was reviewed is what runs. All infra changes go through version control and PR review — no console-clicking that leaves no trail.
5. **Small blast radius** — separate state per environment AND per logical domain (network / data / app). One mega-state means every change risks everything and plans take forever.

## Project layout (environment directories — recommended default)

```
infra/
├── modules/
│   ├── network/        # vpc, subnets
│   ├── k8s-cluster/
│   └── app-service/
├── envs/
│   ├── dev/
│   │   ├── main.tf     # instantiates modules with dev params
│   │   ├── backend.tf  # dev state key
│   │   └── terraform.tfvars
│   └── prod/
│       ├── main.tf
│       ├── backend.tf
│       └── terraform.tfvars
```

Environment directories over workspaces: explicit, diffable, different backend configs, no "which workspace am I in" accidents. Workspaces are fine for ephemeral copies of the SAME config (preview envs).

## Backend example

```hcl
terraform {
  required_version = ">= 1.9"
  backend "s3" {
    bucket       = "myco-tfstate"
    key          = "prod/app/terraform.tfstate"
    region       = "ap-southeast-1"
    encrypt      = true
    use_lockfile = true    # native S3 locking, TF >= 1.10; else dynamodb_table
  }
  required_providers {
    aws = {source = "hashicorp/aws", version = "~> 5.0"}
  }
}
```

## Module design rules

- A module = one cohesive concept with a clean interface, not a thin wrapper around a single resource and not a "everything for this app" grab bag.
- Inputs: typed variables with `description` and `validation` blocks; sensible defaults for optional knobs only.
- Outputs: everything a consumer plausibly needs (IDs, ARNs, endpoints) — adding outputs later forces extra applies.
- Mark secret outputs/variables `sensitive = true`.
- No provider blocks inside reusable modules (pass providers from root).
- Prefer declarative composition over imperative CLI scripts (Terraform over `aws cli` one-offs) — declarative infra is what makes plans meaningful.

## Working with existing infrastructure

- `terraform import` (or `import` blocks, TF ≥1.5, which plan the import — much safer) to adopt click-created resources.
- `terraform state mv` when refactoring module structure — avoids destroy/recreate. Check the plan says "no changes" after a pure refactor.
- Never hand-edit state. For surgery: `state rm` + import, or `moved {}` blocks.

## CI pattern for Terraform

```yaml
# PR: fmt check + validate + plan (posted to PR)
- terraform fmt -check -recursive
- terraform init -backend-config=envs/prod/backend.hcl
- terraform validate
- terraform plan -var-file=envs/prod/terraform.tfvars -out=tfplan
# merge to main: apply the reviewed plan artifact
- terraform apply tfplan
```

Add `tflint` and `trivy config` (or `checkov`) as advisory jobs. Use OIDC to the cloud provider — Terraform in CI with static admin keys is the single riskiest credential most orgs have. Least-privilege IAM for the CI role: scope it to only the resources/actions the plan actually needs.

## Design for failure

- Data-holding resources (RDS, buckets): set deletion protection at both TF and cloud level; plan for `skip_final_snapshot = false`. Protect crown jewels with `lifecycle { prevent_destroy = true }`.
- Drift: schedule `terraform plan -detailed-exitcode` as a cron job to detect console-clicking — infra that silently drifts from code is infra you can no longer trust the plan for.
- Every apply should be reversible in principle: know how you'd revert a bad plan (revert the commit + re-apply, or `state` surgery for anything `prevent_destroy` doesn't cover).

## Common pitfalls

- `count` vs `for_each`: prefer `for_each` with stable keys — with `count`, removing item 0 recreates every subsequent resource.
- Unintended destroys: read plans carefully before approving an apply.
- Provider-inferred changes flapping every plan → missing `ignore_changes` for fields mutated out-of-band (e.g., autoscaled `desired_count`).

## Output quality bar

- Deliver complete, runnable `.tf` files — not fragments with `# ... rest of config` placeholders. Include the commands to plan/apply/verify.
- Add brief comments explaining *why* for non-obvious choices (e.g., why `prevent_destroy`, why a specific `ignore_changes`) — not narrating HCL syntax.
- When multiple valid approaches exist (workspaces vs env directories, module boundary choices), pick one, deliver it, and mention the main alternative in one sentence with the tradeoff.
- After generating, mentally dry-run the plan: do variable types and defaults line up with how the module is invoked? Do outputs a consumer needs actually exist?

## Anti-patterns to actively avoid

- Terraform without remote state + locking for any team context.
- Local `terraform.tfstate` committed to git, or state files containing plaintext secrets left unprotected.
- Hardcoded credentials/access keys in `.tf` or `.tfvars` files instead of a secret manager or CI OIDC.
- Copy-pasting a "kitchen sink" module with resources/features the user didn't ask for and doesn't need.
