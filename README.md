# templates

Project starters, one directory each.

Every template here is a **documented placeholder**. The structure, the contracts
and the conventions are in place; the logic is not. Signatures have docstrings and
numbered `TODO` steps, bodies raise `NotImplementedError`, documents have sections
and guidance notes with the content left blank. The scaffolding is the deliverable —
you fill in the project.

| Template | Stack |
|---|---|
| [machine-learning](machine-learning/) | uv · Hydra · DVC · MLflow · FastAPI/Streamlit — leakage-safe ML project structure with sectioned notebooks and shared split/metric modules |
| [docs](docs/) | Markdown — enterprise-standard README, plus the SECURITY, CONTRIBUTING, CHANGELOG and ADR documents it links out to |
| backend | *planned* |
| frontend | *planned* |
| data-engineering | *planned* |

## Using a code template

Copy the directory into a new repository and work through its own README, which
covers setup, the order to implement things in, and the rules that template
enforces.

```bash
cp -r templates/machine-learning my-new-project
cd my-new-project && git init
```

## Using the docs templates

[`docs/`](docs/) is different from the others: it is not a project skeleton but a
set of documents to drop into any project, whatever the stack.

| File | Copy to | Purpose |
|---|---|---|
| [README.template.md](docs/README.template.md) | `README.md` | The main deliverable. Architecture, configuration, security posture, ownership, SLOs, versioning policy |
| [SECURITY.template.md](docs/SECURITY.template.md) | `SECURITY.md` | Supported versions, private reporting channel, response times, disclosure |
| [CONTRIBUTING.template.md](docs/CONTRIBUTING.template.md) | `CONTRIBUTING.md` | Setup, commit and branch conventions, PR requirements, review SLA |
| [CHANGELOG.template.md](docs/CHANGELOG.template.md) | `CHANGELOG.md` | Keep a Changelog skeleton with a worked release entry |
| [adr/README.template.md](docs/adr/README.template.md) | `docs/adr/README.md` | When a decision warrants a record, the lifecycle, and the index |
| [adr/0000-record-architecture-decisions.md](docs/adr/0000-record-architecture-decisions.md) | `docs/adr/0000-…md` | The record format — and, as written, a real first ADR |
| [CLAUDE.template.md](docs/CLAUDE.template.md) | `CLAUDE.md` | Instructions for Claude Code: the working agreement it must follow, plus the commands, architecture and conventions it cannot infer |
| [USECASE_SPECIFICATION.html](docs/USECASE_SPECIFICATION.html) | `docs/USECASE_SPECIFICATION.html` | The document written before the code: overview and positioning, goals, stakeholders, functional and non-functional requirements, and a use case block per interaction. Self-contained dark-theme HTML — opens in a browser, prints to PDF for sign-off |

```bash
cp docs/README.template.md        my-project/README.md
cp docs/CLAUDE.template.md        my-project/CLAUDE.md
cp docs/SECURITY.template.md      my-project/SECURITY.md
cp docs/CONTRIBUTING.template.md  my-project/CONTRIBUTING.md
cp docs/CHANGELOG.template.md     my-project/CHANGELOG.md
mkdir -p my-project/docs/adr
cp docs/adr/README.template.md    my-project/docs/adr/README.md
cp docs/adr/0000-*.md             my-project/docs/adr/
cp docs/USECASE_SPECIFICATION.html my-project/docs/
```

Relative links inside the templates — `SECURITY.md`, `docs/adr/`,
`.github/CODEOWNERS` — are written for the **destination** project root, not for
this repository. They resolve once the files are copied into place; they are not
broken links to fix here.

The `.template.md` suffix is dropped on the way. It exists because GitHub
auto-discovers `SECURITY.md` and `CONTRIBUTING.md` in the repository root, in
`.github/`, **and** in `docs/` — without the suffix, this repository would publish
a blank template as its own security policy.

### The two conventions

**Placeholders** are `<SCREAMING_SNAKE_CASE>` in angle brackets, so one command
tells you whether a copy is finished:

```bash
grep -n '<[A-Z][A-Z0-9_]*>' README.md      # must return nothing
```

[USECASE_SPECIFICATION.html](docs/USECASE_SPECIFICATION.html) is the one
exception: being HTML, it escapes its placeholders as `&lt;NAME&gt;` — an
unescaped one would be parsed as a tag and vanish from the rendered page — so its
check is `grep -n '&lt;[A-Z][A-Z0-9_]*&gt;'`. For the same reason its markers are
visible boxes on the page rather than HTML comments, which nobody reading in a
browser would see. It needs no `.template` suffix: GitHub auto-discovers only
`SECURITY.md` and `CONTRIBUTING.md`.

**Markers** in HTML comments say whether a section applies to you. They never
render, and they are deleted along with the sections they govern:

| Marker | Meaning |
|---|---|
| `<!-- REQUIRED-IF: … -->` | Keep when the condition holds; otherwise delete the whole section |
| `<!-- OPTIONAL: … -->` | Judgement call; default to deleting |
| `<!-- GUIDANCE: … -->` | What belongs in the section and what does not. Always deleted before publishing |

No section is silently optional. A section with no marker is required — so a
reviewer can tell a deliberate omission from an oversight.

Each template closes with a **before you publish** checklist. Work through it and
delete it.

### Which optional sections you actually need

The judgement call people get wrong most often. Sections not listed are required
for every project.

| Section | Library / SDK | Deployed service | Data pipeline | CLI tool |
|---|---|---|---|---|
| Build and deployment | delete — cover releases under Versioning | **required** | **required** | keep, for the publish and distribution path |
| Observability | delete | **required** | **required** — run status and data-freshness alerting are the point | delete |
| Compliance and data handling | delete, unless it processes personal data itself | **required** if it touches personal, payment or health data | **required** — this is usually the section that matters most | delete |
| Service levels and support | delete | keep for internal-platform or customer-facing; delete for internal tooling | keep — freshness and completeness are the SLIs | delete |
| Feature flags | delete | keep if used | delete | delete |
| Roadmap | keep only if you will maintain it — a stale roadmap makes every other section look stale | | | |

The two sections nobody should delete on grounds of size: **Non-goals**, because
it prevents work rather than describing it, and **Rollback**, because it is read
under pressure by someone who has never deployed the thing.

## License

MIT — see [LICENSE](LICENSE).
