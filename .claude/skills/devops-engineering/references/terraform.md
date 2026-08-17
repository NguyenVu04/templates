# Terraform & Infrastructure as Code

## Non-negotiables for any team/production usage

1. **Remote state with locking** — S3+DynamoDB (or S3 native locking in TF ≥1.10), GCS, Azure Blob, or Terraform Cloud. Local state = guaranteed eventual disaster (lost laptop, concurrent applies, secrets in plaintext on disk).
2. **State contains secrets in plaintext** — treat the state backend as a secret store: encrypt at rest, restrict access, never commit `terraform.tfstate` (gitignore it plus `.terraform/`).
3. **Pin versions** — `required_version` for Terraform, version constraints for every provider (`~> 5.0`), commit `.terraform.lock.hcl`.
4. **Plan before apply, always** — in CI: `plan` on PR (posted as comment), `apply` only on merge to main, from the saved plan artifact (`terraform apply tfplan`) so what was reviewed is what runs.
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

Add `tflint` and `trivy config` (or `checkov`) as advisory jobs. Use OIDC to the cloud provider — Terraform in CI with static admin keys is the single riskiest credential most orgs have.

## Common pitfalls

- `count` vs `for_each`: prefer `for_each` with stable keys — with `count`, removing item 0 recreates every subsequent resource.
- Unintended destroys: read plans carefully; protect crown jewels with `lifecycle { prevent_destroy = true }`.
- Provider-inferred changes flapping every plan → missing `ignore_changes` for fields mutated out-of-band (e.g., autoscaled `desired_count`).
- Data-holding resources (RDS, buckets): set deletion protection at both TF and cloud level; plan for `skip_final_snapshot = false`.
- Drift: schedule `terraform plan -detailed-exitcode` as a cron job to detect console-clicking.
